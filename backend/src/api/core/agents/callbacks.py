"""Callback that persists one `agent_message_usage` row per LLM call.

The SINGLE accounting point: attached to every registry agent via
`.with_config(callbacks=[usage_recorder])` and passed explicitly in `config["callbacks"]` by
the streaming path and `core/agents/llm.py`. It works on every invocation path (ainvoke,
astream, astream_events), so no call route escapes measurement — a spend cap is only as good
as its coverage.

Flow:
    on_chat_model_start  -> stash RunnableConfig.metadata per run_id
    on_llm_end           -> read usage_metadata of the final AIMessage, compute cost, insert
    on_llm_error         -> only drop the stash (no memory leak)

Expected RunnableConfig.metadata (build it with `UsageContext.to_metadata()` from `llm.py`):
    - thread_id   (required; without it no row is written)
    - agent_id    (required)
    - user_id     (optional)
    - client_id   (optional sub-scope, e.g. an end customer)
    - tenant_id   (optional; what per-tenant monthly cost / spend caps sum over — apps map
                   their organization_id here)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from api.core.logging import get_logger
from api.repositories.agents.usage import (
    build_usage_from_ai_message,
    insert_agent_message_usage,
)
from config import database as database_module

log = get_logger(__name__)


class UsageRecorderCallback(AsyncCallbackHandler):
    """Persist agent_message_usage automatically on every `on_llm_end`."""

    def __init__(self) -> None:
        self._meta_by_run: dict[UUID, dict[str, Any]] = {}

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],  # noqa: ARG002
        messages: list[list[Any]],  # noqa: ARG002
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        tags: list[str] | None = None,  # noqa: ARG002
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        if metadata:
            self._meta_by_run[run_id] = dict(metadata)

    async def on_llm_error(
        self,
        error: BaseException,  # noqa: ARG002
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        self._meta_by_run.pop(run_id, None)

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        meta = self._meta_by_run.pop(run_id, {})
        thread_id = meta.get("thread_id")
        agent_id = meta.get("agent_id")
        if not thread_id or not agent_id:
            return

        gens = response.generations
        if not gens or not gens[0]:
            return
        ai_msg = getattr(gens[0][0], "message", None)
        usage_row = build_usage_from_ai_message(
            ai_msg,
            thread_id=str(thread_id),
            message_id=str(getattr(ai_msg, "id", "") or run_id),
            agent_id=str(agent_id),
            user_id=str(meta["user_id"]) if meta.get("user_id") is not None else None,
            client_id=str(meta["client_id"]) if meta.get("client_id") is not None else None,
            tenant_id=str(meta["tenant_id"]) if meta.get("tenant_id") is not None else None,
        )
        if usage_row is None:
            return

        # Own connection, outside any caller transaction: accounting must not be undone by a
        # rollback of the flow that triggered it — the provider already charged the tokens.
        # No pool (scripts, tests without DB) = nothing to record, never an error.
        pool = getattr(database_module, "asyncpg_pool", None)
        if pool is None:
            return
        try:
            async with pool.acquire() as conn:
                await insert_agent_message_usage(conn, usage_row)
        except Exception:
            log.exception(
                "usage_recorder_insert_failed", thread_id=str(thread_id), agent_id=str(agent_id)
            )


usage_recorder = UsageRecorderCallback()
