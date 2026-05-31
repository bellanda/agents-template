"""Custom asyncpg-backed LangGraph checkpointer.

Replaces langgraph-checkpoint-postgres (psycopg-only) so the whole app runs on a
single driver (asyncpg) and reuses the managed connection pool. Ported from
``langgraph.checkpoint.postgres.{base,aio}`` @ langgraph-checkpoint-postgres 3.1.0 —
the serde/version helpers mirror ``BasePostgresSaver`` exactly so checkpoints
written by either implementation stay mutually readable. Keep in sync with that
schema/serde when bumping langgraph; a smoke test guards the round-trip.

Schema (``checkpoints`` / ``checkpoint_blobs`` / ``checkpoint_writes``) is created
by dbmate, never by ``.setup()``. JSONB columns ride the orjson codec registered
on every pool connection (``config.database.init_connection``), so they encode
from / decode to ``dict`` automatically; ``bytea`` maps to ``bytes``.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator, Sequence
from typing import Any

import asyncpg
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_serializable_checkpoint_metadata,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.serde.types import _DeltaSnapshot

# SQL ported from BasePostgresSaver; psycopg %s placeholders rewritten to asyncpg $N.
SELECT_SQL = """
select thread_id, checkpoint, checkpoint_ns, checkpoint_id, parent_checkpoint_id, metadata,
  (select array_agg(array[bl.channel::bytea, bl.type::bytea, bl.blob])
   from jsonb_each_text(checkpoint -> 'channel_versions')
   inner join checkpoint_blobs bl
     on bl.thread_id = checkpoints.thread_id
     and bl.checkpoint_ns = checkpoints.checkpoint_ns
     and bl.channel = jsonb_each_text.key
     and bl.version = jsonb_each_text.value) as channel_values,
  (select array_agg(array[cw.task_id::text::bytea, cw.channel::bytea, cw.type::bytea, cw.blob]
                    order by cw.task_id, cw.idx)
   from checkpoint_writes cw
   where cw.thread_id = checkpoints.thread_id
     and cw.checkpoint_ns = checkpoints.checkpoint_ns
     and cw.checkpoint_id = checkpoints.checkpoint_id) as pending_writes
from checkpoints """

UPSERT_CHECKPOINT_BLOBS_SQL = """
insert into checkpoint_blobs (thread_id, checkpoint_ns, channel, version, type, blob)
values ($1, $2, $3, $4, $5, $6)
on conflict (thread_id, checkpoint_ns, channel, version) do nothing"""

UPSERT_CHECKPOINTS_SQL = """
insert into checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, checkpoint, metadata)
values ($1, $2, $3, $4, $5, $6)
on conflict (thread_id, checkpoint_ns, checkpoint_id)
do update set checkpoint = excluded.checkpoint, metadata = excluded.metadata"""

UPSERT_CHECKPOINT_WRITES_SQL = """
insert into checkpoint_writes
  (thread_id, checkpoint_ns, checkpoint_id, task_id, task_path, idx, channel, type, blob)
values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
on conflict (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
do update set channel = excluded.channel, type = excluded.type, blob = excluded.blob"""

INSERT_CHECKPOINT_WRITES_SQL = """
insert into checkpoint_writes
  (thread_id, checkpoint_ns, checkpoint_id, task_id, task_path, idx, channel, type, blob)
values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
on conflict (thread_id, checkpoint_ns, checkpoint_id, task_id, idx) do nothing"""


class AsyncpgCheckpointSaver(BaseCheckpointSaver[str]):
    """LangGraph checkpointer on asyncpg, sharing the app's managed pool.

    Only the async surface is implemented — the app drives agents via
    ``ainvoke`` / ``astream``. Sync methods keep the base ``NotImplementedError``.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(serde=JsonPlusSerializer())
        self.pool = pool

    # --- version + serde helpers (mirror BasePostgresSaver verbatim) ---

    def get_next_version(self, current: str | None, channel: None = None) -> str:  # noqa: ARG002
        current_v = 0 if current is None else int(current.split(".")[0])
        return f"{current_v + 1:032}.{random.random():016}"

    def _dump_blobs(
        self, thread_id: str, checkpoint_ns: str, values: dict[str, Any], versions: ChannelVersions
    ) -> list[tuple[str, str, str, str, str, bytes | None]]:
        return [
            (
                thread_id,
                checkpoint_ns,
                k,
                str(ver),
                *(self.serde.dumps_typed(values[k]) if k in values else ("empty", None)),
            )
            for k, ver in versions.items()
        ]

    def _load_blobs(self, blob_values: list[Sequence[bytes]] | None) -> dict[str, Any]:
        if not blob_values:
            return {}
        return {
            bytes(k).decode(): self.serde.loads_typed((bytes(t).decode(), bytes(v)))
            for k, t, v in blob_values
            if bytes(t).decode() != "empty"
        }

    def _dump_writes(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        task_id: str,
        task_path: str,
        writes: Sequence[tuple[str, Any]],
    ) -> list[tuple[str, str, str, str, str, int, str, str, bytes]]:
        return [
            (
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                task_id,
                task_path,
                WRITES_IDX_MAP.get(channel, idx),
                channel,
                *self.serde.dumps_typed(value),
            )
            for idx, (channel, value) in enumerate(writes)
        ]

    def _load_writes(self, writes: list[Sequence[bytes]] | None) -> list[tuple[str, str, Any]]:
        return (
            [
                (
                    bytes(tid).decode(),
                    bytes(channel).decode(),
                    self.serde.loads_typed((bytes(t).decode(), bytes(v))),
                )
                for tid, channel, t, v in writes
            ]
            if writes
            else []
        )

    def _load_checkpoint_tuple(self, value: dict[str, Any]) -> CheckpointTuple:
        return CheckpointTuple(
            {
                "configurable": {
                    "thread_id": value["thread_id"],
                    "checkpoint_ns": value["checkpoint_ns"],
                    "checkpoint_id": value["checkpoint_id"],
                }
            },
            {
                **value["checkpoint"],
                "channel_values": {
                    **(value["checkpoint"].get("channel_values") or {}),
                    **self._load_blobs(value["channel_values"]),
                },
            },
            value["metadata"],
            (
                {
                    "configurable": {
                        "thread_id": value["thread_id"],
                        "checkpoint_ns": value["checkpoint_ns"],
                        "checkpoint_id": value["parent_checkpoint_id"],
                    }
                }
                if value["parent_checkpoint_id"]
                else None
            ),
            self._load_writes(value["pending_writes"]),
        )

    def _search_where(
        self,
        config: RunnableConfig | None,
        metadata_filter: dict[str, Any] | None,
        before: RunnableConfig | None,
    ) -> tuple[str, list[Any]]:
        wheres: list[str] = []
        params: list[Any] = []
        if config:
            params.append(config["configurable"]["thread_id"])
            wheres.append(f"thread_id = ${len(params)}")
            checkpoint_ns = config["configurable"].get("checkpoint_ns")
            if checkpoint_ns is not None:
                params.append(checkpoint_ns)
                wheres.append(f"checkpoint_ns = ${len(params)}")
            if checkpoint_id := get_checkpoint_id(config):
                params.append(checkpoint_id)
                wheres.append(f"checkpoint_id = ${len(params)}")
        if metadata_filter:
            params.append(metadata_filter)
            wheres.append(f"metadata @> ${len(params)}::jsonb")
        if before is not None:
            params.append(get_checkpoint_id(before))
            wheres.append(f"checkpoint_id < ${len(params)}")
        return ("WHERE " + " AND ".join(wheres) if wheres else "", params)

    # --- async DB surface (asyncpg) ---

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = get_checkpoint_id(config)
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        async with self.pool.acquire() as conn:
            if checkpoint_id:
                row = await conn.fetchrow(
                    SELECT_SQL
                    + "WHERE thread_id = $1 AND checkpoint_ns = $2 AND checkpoint_id = $3",
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                )
            else:
                row = await conn.fetchrow(
                    SELECT_SQL + "WHERE thread_id = $1 AND checkpoint_ns = $2 "
                    "ORDER BY checkpoint_id DESC LIMIT 1",
                    thread_id,
                    checkpoint_ns,
                )
        return self._load_checkpoint_tuple(dict(row)) if row else None

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,  # noqa: A002
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        where, params = self._search_where(config, filter, before)
        query = SELECT_SQL + where + " ORDER BY checkpoint_id DESC"
        if limit is not None:
            params.append(int(limit))
            query += f" LIMIT ${len(params)}"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        for row in rows:
            yield self._load_checkpoint_tuple(dict(row))

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        configurable = config["configurable"].copy()
        thread_id = configurable.pop("thread_id")
        checkpoint_ns = configurable.pop("checkpoint_ns")
        checkpoint_id = configurable.pop("checkpoint_id", None)

        copy = checkpoint.copy()
        copy["channel_values"] = copy["channel_values"].copy()

        # Inline primitives into the checkpoint row; everything else goes to blobs.
        blob_values: dict[str, Any] = {}
        for k, v in checkpoint["channel_values"].items():
            if isinstance(v, _DeltaSnapshot):
                blob_values[k] = copy["channel_values"].pop(k)
                copy["channel_values"][k] = True
            elif v is None or isinstance(v, str | int | float | bool):
                pass
            else:
                blob_values[k] = copy["channel_values"].pop(k)

        blob_versions = {k: v for k, v in new_versions.items() if k in blob_values}
        async with self.pool.acquire() as conn, conn.transaction():
            if blob_versions:
                await conn.executemany(
                    UPSERT_CHECKPOINT_BLOBS_SQL,
                    self._dump_blobs(thread_id, checkpoint_ns, blob_values, blob_versions),
                )
            await conn.execute(
                UPSERT_CHECKPOINTS_SQL,
                thread_id,
                checkpoint_ns,
                checkpoint["id"],
                checkpoint_id,
                copy,
                get_serializable_checkpoint_metadata(config, metadata),
            )
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        query = (
            UPSERT_CHECKPOINT_WRITES_SQL
            if all(w[0] in WRITES_IDX_MAP for w in writes)
            else INSERT_CHECKPOINT_WRITES_SQL
        )
        params = self._dump_writes(
            config["configurable"]["thread_id"],
            config["configurable"]["checkpoint_ns"],
            config["configurable"]["checkpoint_id"],
            task_id,
            task_path,
            writes,
        )
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.executemany(query, params)

    async def adelete_thread(self, thread_id: str) -> None:
        async with self.pool.acquire() as conn, conn.transaction():
            for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
                await conn.execute(f"DELETE FROM {table} WHERE thread_id = $1", str(thread_id))
