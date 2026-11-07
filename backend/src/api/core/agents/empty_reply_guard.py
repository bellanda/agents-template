"""Model-call middleware: a turn must never end with no customer-facing text after a tool.

Prod/replay 2026-11-05: after a tool whose result read like a completion receipt ("Registrado.")
Haiku sometimes stops with an EMPTY message, so the customer gets silence. The tool texts now say
explicitly that the reply is still owed; this guard is the safety net: one retry with an explicit
instruction. The instruction lives only in the retried request (never persisted in the thread).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

log = structlog.get_logger(__name__)

EMPTY_REPLY_RETRY_INSTRUCTION = (
    "[sistema] Você terminou a ação mas não escreveu NENHUMA mensagem para o cliente. "
    "Escreva agora a resposta dele, curta, seguindo as regras do prompt."
)


def is_empty_final_after_tool(request_messages: list[Any], response: ModelResponse[Any]) -> bool:
    """True when the model answered a ToolMessage with no text and no further tool call."""
    if not request_messages or not isinstance(request_messages[-1], ToolMessage):
        return False
    ai_messages = [m for m in response.result if isinstance(m, AIMessage)]
    if not ai_messages:
        return False
    last = ai_messages[-1]
    return not last.tool_calls and not _text_of(last.content).strip()


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block) for block in content
        )
    return ""


class EmptyReplyGuardMiddleware(AgentMiddleware):
    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        response = await handler(request)
        if not is_empty_final_after_tool(request.messages, response):
            return response
        log.warning("agent_empty_reply", tool=getattr(request.messages[-1], "name", None))
        retry_messages = [*request.messages, HumanMessage(content=EMPTY_REPLY_RETRY_INSTRUCTION)]
        return await handler(request.override(messages=retry_messages))


empty_reply_guard_middleware = EmptyReplyGuardMiddleware()
