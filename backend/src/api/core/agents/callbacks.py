"""Callback que persiste uma linha em agent_message_usage por chamada de LLM.

Anexado a todo agente no registry via `.with_config(callbacks=[usage_recorder])`.
Funciona com qualquer caminho de invocação (ainvoke, astream, astream_events) e
em qualquer agente — é o ponto único de contabilização.

Fluxo:
    on_chat_model_start  -> guarda metadata por run_id
    on_llm_end           -> extrai usage_metadata da AIMessage final, calcula custo
                            via tabela de preços e insere uma linha
    on_llm_error         -> só limpa o cache de metadata pra não vazar memória

Metadata esperado em RunnableConfig.metadata:
    - thread_id   (obrigatório; sem ele a linha não é gravada)
    - agent_id    (obrigatório)
    - user_id     (opcional)
    - client_id   (opcional)
"""

from __future__ import annotations

from traceback import format_exc
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from api.repositories.agents.usage import (
    build_usage_from_ai_message,
    insert_agent_message_usage,
)
from config import database as database_module


class UsageRecorderCallback(AsyncCallbackHandler):
    """Persiste agent_message_usage automaticamente em todo `on_llm_end`."""

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
        )
        if usage_row is None:
            return

        pool = getattr(database_module, "asyncpg_pool", None)
        if pool is None:
            return
        try:
            async with pool.acquire() as conn:
                await insert_agent_message_usage(conn, usage_row)
        except Exception:
            print(f"[UsageRecorderCallback] insert failed\n{format_exc()}")


usage_recorder = UsageRecorderCallback()
