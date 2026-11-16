"""Regression tests for audit 2026-11-13 infra-live-06 / core-performance-05 (no DB, no NATS)."""

import asyncio
from dataclasses import dataclass, field

import anyio
import pytest

from api.services.messaging import consumer_support, consumers


@dataclass  # eq=True makes it unhashable, like nats-py `Msg`
class FakeMsg:
    is_acked: bool = False
    naks: list[float] = field(default_factory=list)

    async def nak(self, delay: float = 0.0) -> None:
        self.naks.append(delay)
        self.is_acked = True


class FakeSub:
    def __init__(self, msgs: list[FakeMsg] | None = None) -> None:
        self.msgs = msgs
        self.timeouts: list[float] = []

    async def fetch(self, batch: int, timeout: float) -> list[FakeMsg]:
        self.timeouts.append(timeout)
        if self.msgs is not None:
            return self.msgs
        await anyio.sleep(timeout)
        raise TimeoutError


@pytest.fixture(autouse=True)
def _clean_inflight():
    consumer_support._INFLIGHT.clear()
    yield
    consumer_support._INFLIGHT.clear()


def test_idle_timeout_is_long() -> None:
    assert consumer_support.IDLE_FETCH_TIMEOUT_SECONDS >= 20.0


async def test_fetch_returns_promptly_when_stop_is_set() -> None:
    stop, sub = anyio.Event(), FakeSub()
    task = asyncio.create_task(consumer_support.fetch_until_stop(sub, stop, batch=1, timeout=30.0))
    await asyncio.sleep(0.05)
    stop.set()
    assert await asyncio.wait_for(task, timeout=2) == []


async def test_fetch_propagates_empty_queue_timeout() -> None:
    with pytest.raises(TimeoutError):
        await consumer_support.fetch_until_stop(FakeSub(), anyio.Event(), batch=1, timeout=0.05)


async def test_unsettled_inflight_is_naked_with_zero_delay() -> None:
    settled, orphan = FakeMsg(), FakeMsg()
    await consumer_support.fetch_until_stop(FakeSub([settled, orphan]), anyio.Event(), batch=2)
    settled.is_acked = True
    assert await consumer_support.nak_unsettled_inflight() == 1
    assert orphan.naks == [0.0] and settled.naks == []


async def test_stop_consumers_naks_cancelled_handler_message(monkeypatch) -> None:
    monkeypatch.setattr(consumers, "STOP_GRACE_SECONDS", 0.1)
    msg = FakeMsg()

    async def slow_consumer(stop: anyio.Event) -> None:
        await consumer_support.fetch_until_stop(FakeSub([msg]), stop, batch=1)
        await asyncio.sleep(30)  # handler outliving the grace period

    monkeypatch.setattr(consumers, "_CONSUMER_ENTRYPOINTS", (("slow", slow_consumer),))
    await consumers.start_consumers()
    await asyncio.sleep(0.05)
    await consumers.stop_consumers()
    assert msg.naks == [0.0]
