"""`entity.changed` publisher: wire shape, actor exclusion, best-effort (audit 2026-11-13 core-spa-05)."""

import pytest

from api.services.realtime import entity_events
from api.services.realtime.entity_events import entity_changed_event, publish_entity_changed


class RecordingBus:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[list, dict]] = []
        self.fail = fail

    async def publish_many(self, user_ids, event):
        if self.fail:
            raise RuntimeError("nats down")
        self.calls.append((list(user_ids), event))


def test_wire_shape_is_a_signal_with_string_ids():
    assert entity_changed_event("approval", "org-1", [7, 8]) == {
        "type": "entity.changed",
        "payload": {"entity": "approval", "org_id": "org-1", "ids": ["7", "8"]},
    }
    assert "ids" not in entity_changed_event("approval", "org-1")["payload"]


@pytest.mark.asyncio
async def test_actor_is_excluded_and_nobody_to_tell_publishes_nothing(monkeypatch):
    bus = RecordingBus()
    monkeypatch.setattr(entity_events, "event_bus", bus)
    await publish_entity_changed([1, 2, 3], "kit", "org-1", exclude_user_id=2)
    assert bus.calls[0][0] == [1, 3]
    await publish_entity_changed([2], "kit", "org-1", exclude_user_id=2)
    assert len(bus.calls) == 1


@pytest.mark.asyncio
async def test_publish_failure_never_raises(monkeypatch):
    monkeypatch.setattr(entity_events, "event_bus", RecordingBus(fail=True))
    await publish_entity_changed([1], "kit", "org-1")
