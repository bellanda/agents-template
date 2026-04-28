"""Sliding-window middleware that trims the message list sent to the LLM per turn.

The LangGraph checkpoint persists the *full* conversation indefinitely, which is what
the UI replays. But when the next turn fires, that whole history is also re-shipped to
the model — and tool results from earlier turns dominate token cost. This middleware
intercepts each model call and substitutes a trimmed view of the history while leaving
the persisted state untouched.

Strategy:
- Always keep the system message (handled outside, in `request.system_message`).
- Always keep messages from the *current* turn intact (everything after the last
  `HumanMessage`).
- Walk older turns from newest to oldest, keeping `HumanMessage` / `AIMessage` content
  but replacing the heavy `output` of older `ToolMessage` records with a short
  placeholder so the model sees what was asked but not the 5KB JSON payload.
- Stop once the rough token estimate (`len(content) / 4`) exceeds
  `MAX_TOKENS_HEURISTIC` or once `MAX_MESSAGES_TO_LLM` is reached.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    ToolMessage,
)

# ──────────────────────────────────────────────────────────────────────────────
# Tuning knobs — keep them generous enough to preserve recent context, tight
# enough to stop runaway growth after long sessions.
# ──────────────────────────────────────────────────────────────────────────────
MAX_MESSAGES_TO_LLM: int = 24
MAX_TOKENS_HEURISTIC: int = 30_000
TOKEN_HEURISTIC_DIVISOR: int = 4
TOOL_RESULT_PLACEHOLDER: str = (
    "[resultado de turno anterior omitido para economizar contexto — "
    "se precisar dele de novo, peça ao usuário ou chame a tool novamente]"
)


def _content_length(message: AnyMessage) -> int:
    content = getattr(message, "content", "") or ""
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for part in content:
            if isinstance(part, str):
                total += len(part)
            elif isinstance(part, dict):
                total += len(str(part.get("text") or part.get("content") or part))
        return total
    return len(str(content))


def _replace_tool_message(message: ToolMessage) -> ToolMessage:
    """Return a lighter copy of a ToolMessage where heavy output is masked."""
    return ToolMessage(
        content=TOOL_RESULT_PLACEHOLDER,
        tool_call_id=message.tool_call_id,
        name=message.name,
        status=getattr(message, "status", None) or "success",
    )


def _find_current_turn_start(messages: list[AnyMessage]) -> int:
    """Index of the last HumanMessage — anything from there forward is 'this turn'."""
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return index
    return 0


def trim_messages_for_llm(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Apply the sliding-window strategy. Pure function, no side effects on input list."""
    if not messages:
        return messages

    current_turn_start = _find_current_turn_start(messages)
    current_turn = messages[current_turn_start:]
    previous_turns = messages[:current_turn_start]

    # Token budget already consumed by the current turn (we never trim it).
    consumed_tokens = sum(_content_length(msg) for msg in current_turn) // TOKEN_HEURISTIC_DIVISOR
    remaining_budget = max(0, MAX_TOKENS_HEURISTIC - consumed_tokens)

    kept_previous: list[AnyMessage] = []
    for message in reversed(previous_turns):
        adjusted = _replace_tool_message(message) if isinstance(message, ToolMessage) else message
        cost = _content_length(adjusted) // TOKEN_HEURISTIC_DIVISOR
        if cost > remaining_budget and kept_previous:
            break
        if len(kept_previous) >= MAX_MESSAGES_TO_LLM - len(current_turn):
            break
        kept_previous.append(adjusted)
        remaining_budget -= cost

    kept_previous.reverse()

    # Guarantee the trimmed prefix doesn't start with an orphan ToolMessage —
    # Gemini rejects ToolMessages that lack a preceding AIMessage with tool_calls.
    while kept_previous and isinstance(kept_previous[0], ToolMessage):
        kept_previous.pop(0)

    return [*kept_previous, *current_turn]


class SlidingWindowMiddleware(AgentMiddleware):
    """Reuse across agents: drop in via ``create_agent(middleware=[SlidingWindowMiddleware()])``."""

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        trimmed = trim_messages_for_llm(request.messages)
        if trimmed is request.messages or len(trimmed) == len(request.messages):
            return await handler(request)
        return await handler(request.override(messages=trimmed))

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        trimmed = trim_messages_for_llm(request.messages)
        if trimmed is request.messages or len(trimmed) == len(request.messages):
            return handler(request)
        return handler(request.override(messages=trimmed))


sliding_window_middleware = SlidingWindowMiddleware()
