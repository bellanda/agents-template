"""`nak_or_exhaust`: NAK with backoff, TERM + `consumer_exhausted` log on the last delivery (no DB, no NATS).

Fleet pattern (kailos audit 2026-11-13 kailos-be-platform-pipelines-2-04): JetStream drops a message
after `max_deliver` attempts without telling anyone, so every consumer settles a failed handler
through this helper instead of a bare `msg.nak()`.
"""

from structlog.testing import capture_logs

from api.services.messaging import consumer_support


class FakeMetadata:
    def __init__(self, num_delivered: int) -> None:
        self.num_delivered = num_delivered


class FakeMsg:
    def __init__(self, delivered: int, subject: str = "x.y") -> None:
        self.metadata = FakeMetadata(delivered)
        self.subject = subject
        self.naks: list[float] = []
        self.terms = 0

    async def nak(self, delay: float = 0.0) -> None:
        self.naks.append(delay)

    async def term(self) -> None:
        self.terms += 1


async def test_nak_or_exhaust_naks_before_the_last_delivery_and_terms_on_it() -> None:
    early, last = FakeMsg(2), FakeMsg(5)
    hooks: list[str] = []

    async def hook() -> None:
        hooks.append("safety-net")

    with capture_logs() as logs:
        assert not await consumer_support.nak_or_exhaust(
            early, durable="d", max_deliver=5, nak_delay=7.0, on_exhausted=hook
        )
        assert await consumer_support.nak_or_exhaust(
            last, durable="d", max_deliver=5, nak_delay=7.0, on_exhausted=hook
        )

    assert early.naks == [7.0] and early.terms == 0
    assert last.naks == [] and last.terms == 1 and hooks == ["safety-net"]
    exhausted = [e for e in logs if e["event"] == "consumer_exhausted"]
    assert len(exhausted) == 1 and exhausted[0]["delivery"] == 5
    assert "payload" not in exhausted[0] and "data" not in exhausted[0]  # customer data stays out


async def test_a_failing_safety_net_hook_does_not_stop_the_term() -> None:
    last = FakeMsg(3)

    async def broken() -> None:
        raise RuntimeError("db down")

    assert await consumer_support.nak_or_exhaust(
        last, durable="d", max_deliver=3, nak_delay=1.0, on_exhausted=broken
    )
    assert last.terms == 1


async def test_missing_metadata_is_treated_as_not_exhausted() -> None:
    msg = FakeMsg(1)
    msg.metadata = None  # type: ignore[assignment]
    assert not await consumer_support.nak_or_exhaust(msg, durable="d", max_deliver=1, nak_delay=2.0)
    assert msg.naks == [2.0] and msg.terms == 0
