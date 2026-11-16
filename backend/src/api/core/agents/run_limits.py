"""Hard bounds for ONE agent turn: step cap (LangGraph recursion_limit) and wall-clock timeout.

Audit 2026-11-13 core-ai-09. LangGraph's default `recursion_limit` is 10007: an agent stuck in a
tool loop keeps calling the model (and spending) until the HTTP connection drops. Every entry
point that runs an agent (streaming chat, non-streaming `execute_agent`, job runners) merges
`run_limits_config()` into its RunnableConfig and bounds the turn with `bounded_events` /
`asyncio.timeout(turn_timeout_seconds())`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from config.settings import settings

# pt-BR texts shown to the user when a turn is cut; the technical detail goes to the log.
TURN_TIMEOUT_USER_MESSAGE = "A resposta demorou demais e foi interrompida. Tente novamente."
TURN_STEP_LIMIT_USER_MESSAGE = (
    "O assistente atingiu o limite de passos desta resposta. Reformule o pedido e tente de novo."
)


def run_limits_config() -> dict[str, Any]:
    """Fragment to merge into the RunnableConfig of an agent turn."""
    return {"recursion_limit": settings.agents.agent_recursion_limit}


def turn_timeout_seconds() -> float:
    return settings.agents.agent_turn_timeout_seconds


async def bounded_events[E](events: AsyncIterator[E], timeout_seconds: float) -> AsyncIterator[E]:
    """Yield from `events` but raise `TimeoutError` once the WHOLE turn exceeds the deadline.

    Per-event `wait_for` instead of a cancel scope around the consumer's loop: a cancel scope
    that stays open across `yield` is unsafe in an async generator. The deadline is for the turn,
    not per event, so a model that trickles tokens forever is also cut.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    iterator = events.__aiter__()
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError(f"agent turn exceeded {timeout_seconds:.0f}s")
            try:
                event = await asyncio.wait_for(iterator.__anext__(), timeout=remaining)
            except StopAsyncIteration:
                return
            yield event
    finally:
        aclose = getattr(iterator, "aclose", None)
        if aclose is not None:
            await aclose()
