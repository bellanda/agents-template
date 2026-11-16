"""Shared plumbing for JetStream pull consumers (audit 2026-11-13: infra-live-06, core-performance-05).

Two problems solved here, once, for every consumer of the app:

1. `fetch_until_stop` - long-poll fetch. Every Granian worker boots EVERY consumer, and each one
   used to poll with a 1 s timeout: ~31 consumers x 8 workers = ~250 pull requests/s with the
   platform idle (kailos NATS: 95 M messages in 2 days with an empty queue). The server answers a
   pull request the instant a message arrives, so a long timeout costs no latency; the only thing
   the short timeout bought was a prompt reaction to the stop event, and `fetch_until_stop` keeps
   that by racing the fetch against the event.

2. `nak_unsettled_inflight` - the stop path (worker recycle every 2 h, deploy) cancels handlers
   that outlive `STOP_GRACE_SECONDS`. A cancelled handler never acks/naks (cancellation is a
   BaseException and the handlers only catch Exception), so JetStream only redelivered after
   `ack_wait` (60 s): the customer waited a minute and the LLM turn was paid twice. Every message
   a consumer fetches through `fetch_until_stop` is remembered here; after the handlers are
   cancelled the supervisor NAKs (delay 0) whatever is still unsettled, so another worker takes
   it at once. Handlers must stay idempotent (they already are: JetStream is at-least-once).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import anyio
import structlog

log = structlog.get_logger(__name__)

# A pull request that finds the stream empty is parked on the server until a message arrives or
# this expires. 25 s keeps the idle rate at ~2 requests/min per consumer.
IDLE_FETCH_TIMEOUT_SECONDS = 25.0

# Messages handed out by `fetch_until_stop` that no handler has settled yet.
# Keyed by id(): nats-py `Msg` is an eq=True dataclass, hence unhashable.
_INFLIGHT: dict[int, Any] = {}


def _prune_settled() -> None:
    """Drop messages already acked/naked/termed (nats-py flips `is_acked` on each of them)."""
    for key in [k for k, m in _INFLIGHT.items() if getattr(m, "is_acked", False)]:
        del _INFLIGHT[key]


async def fetch_until_stop(
    sub: Any,
    stop_event: anyio.Event,
    *,
    batch: int,
    timeout: float = IDLE_FETCH_TIMEOUT_SECONDS,
) -> list[Any]:
    """`sub.fetch(batch, timeout)` that returns `[]` as soon as `stop_event` is set.

    Raises exactly what `sub.fetch` raises (`TimeoutError` on an empty queue, `ServiceUnavailableError`,
    ...), so the callers' existing `except` ladders do not change. Cancellation of the caller
    propagates normally.
    """
    if stop_event.is_set():
        return []
    result: list[Any] = []
    error: Exception | None = None

    async with anyio.create_task_group() as tg:

        async def _fetch() -> None:
            nonlocal error
            try:
                result.extend(await sub.fetch(batch=batch, timeout=timeout))
            except Exception as exc:  # re-raised below, outside the task group (no ExceptionGroup)
                error = exc
            tg.cancel_scope.cancel()

        async def _watch_stop() -> None:
            await stop_event.wait()
            tg.cancel_scope.cancel()

        tg.start_soon(_fetch)
        tg.start_soon(_watch_stop)

    if error is not None:
        raise error
    _prune_settled()
    _INFLIGHT.update({id(msg): msg for msg in result})
    return result


async def nak_unsettled_inflight(*, delay: float = 0.0, deadline_seconds: float = 5.0) -> int:
    """NAK every fetched message nobody settled; returns how many were handed back.

    Call it AFTER the handler tasks were cancelled and awaited (so nothing is still running that
    could double-process the redelivery) and BEFORE closing the NATS connection.
    """
    _prune_settled()
    pending = list(_INFLIGHT.values())
    _INFLIGHT.clear()
    naked = 0
    with anyio.CancelScope(shield=True), anyio.move_on_after(deadline_seconds):
        for msg in pending:
            if getattr(msg, "is_acked", False):
                continue
            try:
                await msg.nak(delay=delay)
                naked += 1
            except Exception:
                log.exception("consumer_stop_nak_failed")
    if naked:
        log.info("consumer_stop_inflight_naked", count=naked)
    return naked


async def nak_or_exhaust(
    msg: Any,
    *,
    durable: str,
    max_deliver: int,
    nak_delay: float,
    on_exhausted: Callable[[], Awaitable[None]] | None = None,
) -> bool:
    """Settle a message whose handler raised: NAK it, or give up for good on the last delivery.

    Audit 2026-11-13 kailos-be-platform-pipelines-2-04: after `max_deliver` attempts JetStream
    drops the message without telling anyone, so a Meta webhook / portal job / cron tick vanished
    with only a generic `consumer_handle_failed` line. On the last delivery this logs
    `consumer_exhausted` (subject and delivery count only, never the payload: it carries customer
    data), runs `on_exhausted` (a consumer-specific safety net such as a dead letter row) and
    TERMs the message so it is not left parked on the stream. Returns True when it gave up.
    """
    delivered = msg.metadata.num_delivered if msg.metadata else 0
    if delivered and delivered >= max_deliver:
        log.error("consumer_exhausted", durable=durable, subject=msg.subject, delivery=delivered)
        if on_exhausted is not None:
            try:
                await on_exhausted()
            except Exception:
                log.exception("consumer_exhausted_hook_failed", durable=durable)
        try:
            await msg.term()
        except Exception:
            log.exception("consumer_term_failed", durable=durable)
        return True
    try:
        await msg.nak(delay=nak_delay)
    except Exception:
        log.exception("consumer_nak_failed", durable=durable)
    return False
