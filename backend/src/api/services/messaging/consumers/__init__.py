"""Background NATS consumers bootstrapped in the app lifespan.

- `start_consumers()` spawns one task per entry of `_CONSUMER_ENTRYPOINTS` (empty in the template).
- `stop_consumers()` signals the stop event, waits for cooperative exit and cancels stragglers
  after `STOP_GRACE_SECONDS`. Runs BEFORE `close_nats` in the lifespan.

Add a consumer: create `<domain>_consumer.py` exposing `async def run_forever(stop: anyio.Event)`
and register `("<domain>", <domain>_consumer.run_forever)` below.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import anyio
import structlog

log = structlog.get_logger(__name__)

STOP_GRACE_SECONDS = 5.0

# Task supervision stays on asyncio (create_task/wait/gather) so consumers drain gracefully
# BEFORE close_nats; a single anyio task group cancelled last would close NATS first.
_STOP_EVENT: anyio.Event | None = None
_TASKS: set[asyncio.Task] = set()

_CONSUMER_ENTRYPOINTS: tuple[tuple[str, Callable[[anyio.Event], Awaitable[None]]], ...] = ()


def _on_consumer_done(task: asyncio.Task) -> None:
    _TASKS.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        log.error("consumer_terminated", consumer=task.get_name(), error=repr(exc))


async def start_consumers() -> None:
    global _STOP_EVENT
    if _STOP_EVENT is not None:
        return

    _STOP_EVENT = anyio.Event()
    for name, entrypoint in _CONSUMER_ENTRYPOINTS:
        task = asyncio.create_task(entrypoint(_STOP_EVENT), name=f"consumer:{name}")
        _TASKS.add(task)
        task.add_done_callback(_on_consumer_done)
    log.info(
        "consumers_started",
        count=len(_TASKS),
        consumers=[n for n, _ in _CONSUMER_ENTRYPOINTS],
    )


async def stop_consumers() -> None:
    global _STOP_EVENT
    if _STOP_EVENT is None:
        return
    _STOP_EVENT.set()

    tasks = tuple(_TASKS)
    if tasks:
        _, pending = await asyncio.wait(tasks, timeout=STOP_GRACE_SECONDS)
        if pending:
            log.warning(
                "consumers_stop_timeout",
                grace_seconds=STOP_GRACE_SECONDS,
                pending=[t.get_name() for t in pending],
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    _TASKS.clear()
    _STOP_EVENT = None
    log.info("consumers_stopped")
