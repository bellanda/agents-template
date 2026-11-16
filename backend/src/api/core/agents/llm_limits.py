"""Process-wide LLM concurrency cap + retry of transient provider errors.

Lives in its own leaf module (no import of `llm.py`/`custom_providers.py`) so BOTH the one-shot
helpers (`llm.complete*`) and the chat model class (`ChatOpenRouter`, which every agent uses via
`init_model`) share ONE limiter and ONE retry policy. Audit 2026-11-13 core-ai-04: before this,
the limiter and the backoff only wrapped `complete*`; the agents (WhatsApp attendant, chat) went
straight to the SDK, so a campaign burst fired dozens of unbounded calls and a 429 got a single
SDK retry.

The cap is per PROCESS (an `anyio.CapacityLimiter` in memory): N workers allow N x
`max_concurrent_llm` calls in flight. Size `agents.max_concurrent_llm` from the number of
workers and the provider's rate limit, not as a global number.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator, Awaitable, Callable
from contextvars import ContextVar

import anyio

from api.core.logging import get_logger
from config.settings import settings

log = get_logger(__name__)

_limiter = anyio.CapacityLimiter(settings.agents.max_concurrent_llm)

# Provider queue / momentary unavailability / gateway timeout. 4xx for credential or payload
# is NOT here: repeating an invalid payload returns the same error, only slower.
RETRYABLE_STATUS: frozenset[int] = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
# Fallback when the exception carries no status (connection resets, SDK timeouts).
RETRYABLE_MARKERS: tuple[str, ...] = (
    "rate limit",
    "overloaded",
    "temporarily unavailable",
    "service unavailable",
    "timeout",
    "timed out",
    "connection reset",
    "connection error",
)
BACKOFF_BASE_SECONDS = 1.5
BACKOFF_MAX_SECONDS = 30.0


def _status_code(exc: BaseException) -> int | None:
    for attribute in ("status_code", "http_status", "code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    value = getattr(getattr(exc, "response", None), "status_code", None)
    return value if isinstance(value, int) else None


def is_retryable(exc: BaseException) -> bool:
    """Only what is transient. When in doubt, do NOT retry."""
    status = _status_code(exc)
    if status is not None:
        return status in RETRYABLE_STATUS
    message = str(exc).lower()
    return any(marker in message for marker in RETRYABLE_MARKERS)


def _backoff_seconds(attempt: int) -> float:
    """Exponential with jitter — without jitter N workers retry at the same instant."""
    ceiling = min(BACKOFF_BASE_SECONDS * (2**attempt), BACKOFF_MAX_SECONDS)
    return random.uniform(ceiling / 2, ceiling)  # jitter, not crypto


# True while the current task already runs inside `with_llm_retry`: the chat model must then
# neither re-acquire the limiter (anyio refuses a second token for the same task) nor retry again
# (3 x 3 attempts).
_in_guarded_call: ContextVar[bool] = ContextVar("llm_in_guarded_call", default=False)


def is_guarded() -> bool:
    return _in_guarded_call.get()


async def _retry_loop[R](call: Callable[[], Awaitable[R]], label: str, attempts: int) -> R:
    for attempt in range(attempts):
        try:
            return await call()
        except Exception as exc:
            if not is_retryable(exc) or attempt == attempts - 1:
                raise
            delay = _backoff_seconds(attempt)
            log.warning(
                "llm_call_retry",
                label=label,
                attempt=attempt + 1,
                delay_seconds=round(delay, 2),
                status_code=_status_code(exc),
            )
            await anyio.sleep(delay)
    raise RuntimeError("unreachable: retry loop always returns or raises")


async def with_llm_retry[R](call: Callable[[], Awaitable[R]], *, label: str) -> R:
    """Run `call` under the process limiter, retrying transient provider errors."""
    attempts = max(settings.agents.llm_max_retries, 1)
    async with _limiter:
        token = _in_guarded_call.set(True)
        try:
            return await _retry_loop(call, label, attempts)
        finally:
            _in_guarded_call.reset(token)


async def guarded_stream[C](
    open_stream: Callable[[], AsyncIterator[C]], *, label: str
) -> AsyncIterator[C]:
    """Stream under the process limiter; retry ONLY while no chunk reached the caller.

    A transient failure after the first chunk is not retried: the client already received
    partial text and a replay would duplicate it. The limiter is held for the whole stream (the
    provider connection is busy for that long). Acquired `on_behalf_of` a token object because an
    async generator can be finalised (aclose on cancel) by a different task than the one that
    started it, and a task-bound `async with` would raise on release.
    """
    if is_guarded():
        async for chunk in open_stream():
            yield chunk
        return
    attempts = max(settings.agents.llm_max_retries, 1)
    borrower = object()
    await _limiter.acquire_on_behalf_of(borrower)
    try:
        for attempt in range(attempts):
            started = False
            try:
                async for chunk in open_stream():
                    started = True
                    yield chunk
                return
            except Exception as exc:
                if started or not is_retryable(exc) or attempt == attempts - 1:
                    raise
                delay = _backoff_seconds(attempt)
                log.warning(
                    "llm_stream_retry",
                    label=label,
                    attempt=attempt + 1,
                    delay_seconds=round(delay, 2),
                    status_code=_status_code(exc),
                )
                await anyio.sleep(delay)
    finally:
        _limiter.release_on_behalf_of(borrower)


async def guarded_call[R](call: Callable[[], Awaitable[R]], *, label: str) -> R:
    """Non-streaming model call: reuse the outer guard if there is one, else open it."""
    if is_guarded():
        return await call()
    return await with_llm_retry(call, label=label)
