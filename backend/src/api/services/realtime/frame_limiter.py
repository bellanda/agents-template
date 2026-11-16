"""Per-connection SSE rate cap + coalescing (fleet module: kailos CRM 2030 etapa 0.3b, promoted to the
template by audit 2026-11-13 core-spa-09 / core-performance-11).

WHY: a 2,000-contact campaign publishes thousands of `message.*` events to the manager's
user channel within seconds. Forwarding each one froze the phone and made the inbox refetch
for every frame. This limiter is pure (injected clock, no NATS/asyncio) so the cap is unit-testable.

Contract:
- At most `SSE_MAX_FRAMES_PER_SECOND` frames leave per 1 s window.
- Identical `(type, id)` events within `SSE_COALESCE_SECONDS` collapse into ONE trailing frame
  carrying the latest payload (so a `message.status` sent->delivered->read pair is never lost,
  only merged). Events without an id are never coalesced (no safe identity).
- Frames that exceed the cap are DROPPED and replaced by a single `BATCH_FRAME` emitted at the
  next window with budget: "many changes happened, refetch the affected lists once".
"""

from collections.abc import Callable
from typing import Final

import orjson

SSE_MAX_FRAMES_PER_SECOND: Final = 20
SSE_COALESCE_SECONDS: Final = 1.0
SSE_WINDOW_SECONDS: Final = 1.0
# Wire shape matches the other frames; the client treats it as "resync everything once".
BATCH_FRAME: Final = 'data: {"type":"batch","payload":{"reason":"burst"}}\n\n'

# Payload fields that identify the entity an event is about, most specific first. A product app
# adds the ids of its own signals here (e.g. `order_id`); events with none are never coalesced.
IDENTITY_FIELDS: Final = (
    "message_id",
    "conversation_id",
    "attendance_id",
    "contact_id",
    "order_id",
)
# `entity.changed` identifies itself by (entity, org): a burst for the same pair collapses into the
# latest frame, and the `ids` of the collapsed events are UNIONED into it (audit 2026-11-15
# r2-nexarena-fe-01: keeping only the latest payload lost the middle events' ids). Past
# `MAX_MERGED_IDS` (or when a side carried none) the frame sends `ids: []`, which the client reads
# as "anything of this entity may have changed" (the frame stays small).
ENTITY_CHANGED_TYPE: Final = "entity.changed"
MAX_MERGED_IDS: Final = 50

EventKey = tuple[str, str]


def event_key(event: dict) -> EventKey | None:
    """`(type, id)` of an event, or None when it carries no usable id."""
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None
    if event.get("type") == ENTITY_CHANGED_TYPE and payload.get("entity"):
        return (ENTITY_CHANGED_TYPE, f"entity:{payload['entity']}:{payload.get('org_id')}")
    for field in IDENTITY_FIELDS:
        value = payload.get(field)
        if value is not None:
            return (str(event.get("type")), f"{field}:{value}")
    return None


def merge_entity_changed(held_raw: bytes, new_raw: bytes) -> bytes:
    """`new_raw` with the `ids` of `held_raw` unioned in; `ids: []` when either side has none/too many."""
    try:
        held, new = orjson.loads(held_raw), orjson.loads(new_raw)
        held_ids = held["payload"].get("ids") or []
        new_ids = new["payload"].get("ids") or []
        merged = list(dict.fromkeys([*held_ids, *new_ids]))
        # An id-less side means "unknown ids": the union is unknown too.
        if not held_ids or not new_ids or len(merged) > MAX_MERGED_IDS:
            merged = []
        new["payload"]["ids"] = merged
        return orjson.dumps(new)
    except (orjson.JSONDecodeError, KeyError, TypeError, AttributeError):
        return new_raw


def to_frame(raw: bytes) -> str:
    return f"data: {raw.decode('utf-8')}\n\n"


class FrameLimiter:
    def __init__(
        self,
        clock: Callable[[], float],
        max_frames_per_window: int = SSE_MAX_FRAMES_PER_SECOND,
        coalesce_seconds: float = SSE_COALESCE_SECONDS,
    ) -> None:
        self._clock = clock
        self._cap = max_frames_per_window
        self._coalesce = coalesce_seconds
        self._window_start = clock()
        self._sent = 0
        self._last_sent: dict[EventKey, float] = {}
        self._held: dict[EventKey, bytes] = {}
        self._batch_due = False

    def _roll_window(self, now: float) -> None:
        if now - self._window_start >= SSE_WINDOW_SECONDS:
            self._window_start = now
            self._sent = 0

    def offer(self, raw: bytes) -> list[str]:
        """Frames to send right now for one incoming NATS message."""
        now = self._clock()
        self._roll_window(now)
        try:
            event = orjson.loads(raw)
        except orjson.JSONDecodeError:
            event = {}
        key = event_key(event) if isinstance(event, dict) else None
        if key is not None and now - self._last_sent.get(key, float("-inf")) < self._coalesce:
            held = self._held.get(key)
            if held is not None and key[0] == ENTITY_CHANGED_TYPE:
                raw = merge_entity_changed(held, raw)
            self._held[key] = raw
            return []
        if self._sent >= self._cap:
            self._batch_due = True
            return []
        self._sent += 1
        if key is not None:
            self._last_sent[key] = now
        return [to_frame(raw)]

    def flush(self) -> list[str]:
        """Frames now due without a new message (held trailing frames, pending batch)."""
        now = self._clock()
        self._roll_window(now)
        out: list[str] = []
        for key in [k for k, _ in self._held.items() if now - self._last_sent[k] >= self._coalesce]:
            raw = self._held.pop(key)
            if self._sent >= self._cap:
                self._batch_due = True
                continue
            self._sent += 1
            self._last_sent[key] = now
            out.append(to_frame(raw))
        if self._batch_due and self._sent < self._cap:
            self._sent += 1
            self._batch_due = False
            out.append(BATCH_FRAME)
        self._prune(now)
        return out

    def _prune(self, now: float) -> None:
        # Bounded memory on long-lived connections: identities older than the window can't coalesce.
        if len(self._last_sent) > 4 * self._cap:
            self._last_sent = {
                k: t
                for k, t in self._last_sent.items()
                if now - t < self._coalesce or k in self._held
            }

    def seconds_until_flush(self) -> float | None:
        """How long the generator may block on NATS before flush() has work; None = idle."""
        if not self._held and not self._batch_due:
            return None
        now = self._clock()
        waits = [self._window_start + SSE_WINDOW_SECONDS - now] if self._batch_due else []
        waits += [self._last_sent[k] + self._coalesce - now for k in self._held]
        return max(0.01, min(waits))
