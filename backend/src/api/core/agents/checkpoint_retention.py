"""Prune superseded LangGraph checkpoints of IDLE threads (agent memory housekeeping).

Audit 2026-11-13 core-ai-07 (kailos/emporion/nexarena already had a per-app copy of this; it never
reached the template, so optimuslar and every new app grew one checkpoint row per graph step
forever). LangGraph writes a checkpoint at every step; only the LATEST of each (thread, namespace)
is read to resume a conversation (`aget_tuple`). Older ones only serve the rollback of a turn
still running (`arollback_thread`).

Safety rules:
- only threads whose newest checkpoint is older than ``idle_hours`` (an in-flight turn may still
  need its own checkpoints for rollback);
- the newest checkpoint of every (thread, namespace) always stays;
- blobs are addressed by (channel, version): a blob goes only if no remaining checkpoint cites it,
  so the three DELETEs run in this order inside ONE transaction.

``run_retention_loop`` is started by the app lifespan (`main.py`): once at boot and then every
``interval_hours``. The DELETEs are idempotent, so N workers doing it is wasted work, not
corruption. Apps with a cron-worker may call ``prune_superseded_checkpoints`` from it instead.
"""

from __future__ import annotations

import asyncio

import asyncpg

from api.core.logging import get_logger

log = get_logger(__name__)

IDLE_HOURS = 24
INTERVAL_HOURS = 24

_IDLE_THREADS = """
    SELECT thread_id, checkpoint_ns, max(checkpoint_id) AS latest_id
    FROM checkpoints
    GROUP BY thread_id, checkpoint_ns
    HAVING max(created_at) < now() - ($1::int * INTERVAL '1 hour')
"""

_PRUNE_CHECKPOINTS = f"""
    WITH idle AS ({_IDLE_THREADS})
    DELETE FROM checkpoints c USING idle i
    WHERE c.thread_id = i.thread_id AND c.checkpoint_ns = i.checkpoint_ns
      AND c.checkpoint_id < i.latest_id
"""

_PRUNE_WRITES = f"""
    WITH idle AS ({_IDLE_THREADS})
    DELETE FROM checkpoint_writes w USING idle i
    WHERE w.thread_id = i.thread_id AND w.checkpoint_ns = i.checkpoint_ns
      AND w.checkpoint_id < i.latest_id
"""

_PRUNE_BLOBS = f"""
    WITH idle AS ({_IDLE_THREADS})
    DELETE FROM checkpoint_blobs b USING idle i
    WHERE b.thread_id = i.thread_id AND b.checkpoint_ns = i.checkpoint_ns
      AND NOT EXISTS (
        SELECT 1 FROM checkpoints c, jsonb_each_text(c.checkpoint -> 'channel_versions') e
        WHERE c.thread_id = b.thread_id AND c.checkpoint_ns = b.checkpoint_ns
          AND e.key = b.channel AND e.value = b.version
      )
"""


def _deleted_count(command_status: str) -> int:
    parts = command_status.split()
    return int(parts[-1]) if parts and parts[-1].isdigit() else 0


async def prune_superseded_checkpoints(
    pool: asyncpg.Pool, *, idle_hours: int = IDLE_HOURS
) -> dict[str, int]:
    """Delete superseded checkpoints/writes/blobs of idle threads. Returns the row counts."""
    async with pool.acquire() as conn, conn.transaction():
        checkpoints = _deleted_count(await conn.execute(_PRUNE_CHECKPOINTS, idle_hours))
        writes = _deleted_count(await conn.execute(_PRUNE_WRITES, idle_hours))
        blobs = _deleted_count(await conn.execute(_PRUNE_BLOBS, idle_hours))
    counts = {"checkpoints": checkpoints, "writes": writes, "blobs": blobs}
    if checkpoints + writes + blobs:
        log.info("checkpoint_retention_pruned", **counts)
    return counts


async def run_retention_loop(get_pool, *, interval_hours: int = INTERVAL_HOURS) -> None:
    """Background task: prune at boot, then every ``interval_hours``. Never raises."""
    while True:
        try:
            await prune_superseded_checkpoints(await get_pool())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("checkpoint_retention_failed")
        await asyncio.sleep(interval_hours * 3600)
