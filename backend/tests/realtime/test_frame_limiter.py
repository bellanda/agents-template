"""Per-connection SSE cap + coalescing (fleet module `services/realtime/frame_limiter.py`).

A burst must not become thousands of frames on a phone: the limiter caps frames/s, merges
identical (type, id) events into the latest one, and replaces the excess with ONE batch frame
("refetch once"). Audit 2026-11-13 core-spa-09 / core-performance-11.
"""

import orjson

from api.services.realtime.frame_limiter import (
    BATCH_FRAME,
    MAX_MERGED_IDS,
    SSE_MAX_FRAMES_PER_SECOND,
    FrameLimiter,
)

BURST_SIZE = 1_000


def _event(kind: str, **payload) -> bytes:
    return orjson.dumps({"type": kind, "payload": payload})


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_burst_of_1000_distinct_events_is_capped_and_ends_in_one_batch_frame():
    clock = FakeClock()
    limiter = FrameLimiter(clock)
    frames: list[str] = []
    for i in range(BURST_SIZE):
        frames += limiter.offer(_event("order.created", order_id=f"o{i}"))
    assert len(frames) == SSE_MAX_FRAMES_PER_SECOND
    assert BATCH_FRAME not in frames

    clock.now += 1.0
    assert limiter.flush() == [BATCH_FRAME]
    assert limiter.flush() == []  # one batch, not one per dropped event


def test_same_type_and_id_collapse_into_the_latest_trailing_frame():
    clock = FakeClock()
    limiter = FrameLimiter(clock)
    assert len(limiter.offer(_event("message.status", message_id="m1", status="sent"))) == 1
    assert limiter.offer(_event("message.status", message_id="m1", status="delivered")) == []
    assert limiter.offer(_event("message.status", message_id="m1", status="read")) == []
    clock.now += 1.0
    trailing = limiter.flush()
    assert len(trailing) == 1 and '"status":"read"' in trailing[0]


def test_entity_changed_bursts_merge_per_entity_and_org_without_losing_other_entities():
    clock = FakeClock()
    limiter = FrameLimiter(clock)

    def changed(entity: str, org: str, i: int) -> bytes:
        return _event("entity.changed", entity=entity, org_id=org, ids=[str(i)])

    assert len(limiter.offer(changed("approval", "org-1", 0))) == 1
    for i in range(1, 50):  # same (entity, org): merged, never 50 frames
        assert limiter.offer(changed("approval", "org-1", i)) == []
    # A different entity (or org) is a different identity and goes through at once.
    assert len(limiter.offer(changed("kit", "org-1", 0))) == 1
    assert len(limiter.offer(changed("approval", "org-2", 0))) == 1
    clock.now += 1.0
    trailing = limiter.flush()
    # ids of the merged events are unioned into the trailing frame (r2-nexarena-fe-01)
    assert len(trailing) == 1
    assert orjson.loads(trailing[0].removeprefix("data: "))["payload"]["ids"] == [
        str(i) for i in range(1, 50)
    ]


def test_events_without_an_id_are_never_coalesced():
    limiter = FrameLimiter(FakeClock())
    sent = [limiter.offer(_event("call.incoming")) for _ in range(3)]
    assert [len(s) for s in sent] == [1, 1, 1]


def _held_ids(limiter: FrameLimiter, clock: FakeClock) -> list[str] | None:
    clock.now += 1.0
    (frame,) = limiter.flush()
    return orjson.loads(frame.removeprefix("data: "))["payload"]["ids"]


def test_entity_changed_merge_drops_ids_when_a_side_has_none_or_the_union_is_too_big():
    """audit 2026-11-15 r2-nexarena-fe-01: `ids: []` = "anything may have changed" for the client."""

    def changed(ids) -> bytes:
        payload = {"entity": "registration", "org_id": "o"}
        if ids is not None:
            payload["ids"] = ids
        return _event("entity.changed", **payload)

    clock = FakeClock()
    limiter = FrameLimiter(clock)
    limiter.offer(changed(["a"]))  # leading, sent
    limiter.offer(changed(["b"]))
    limiter.offer(changed(None))  # an id-less event poisons the window
    assert _held_ids(limiter, clock) == []

    clock = FakeClock()
    limiter = FrameLimiter(clock)
    limiter.offer(changed(["a"]))
    for i in range(MAX_MERGED_IDS + 1):
        limiter.offer(changed([f"e{i}"]))
    assert _held_ids(limiter, clock) == []
