"""Per-user SSE fan-out over NATS core pub/sub (fleet module, audit 2026-11-13).

Public contract: `publish(user_id, event)`, `publish_many(user_ids, event)` and
`subscribe(user_id)` (async generator of ready SSE frames, heartbeat included).

Scales horizontally: any backend instance that publishes reaches any instance serving that
user's SSE; NATS does the fan-out.

ONE subscription per connection and a direct `await sub.next_msg(...)` in the loop. The old
design (two subscriptions + `asyncio.create_task` + `asyncio.wait(FIRST_COMPLETED)`) cancelled the
pending task every lap, and a cancelled `next_msg()` can drop a message the NATS client already
took off its internal queue: a silent lost frame (a new order that only shows after F5). With a
single subscription there is nothing to cancel. Org-wide signals therefore become a recipient
LIST (`publish_many`), never a second channel.

Each connection runs a `FrameLimiter` (`frame_limiter.py`): a burst of events cannot flood a
phone, it is capped and merged into a `batch` frame that tells the client to refetch once.

Publishers call AFTER the writer's COMMIT: the client reacts by fetching REST over another
connection, and a frame that arrives before the commit would find the old data.
"""

import time
from collections.abc import AsyncIterator, Iterable
from typing import Any

import orjson
import structlog
from nats.errors import TimeoutError as NatsTimeoutError

from api.services.messaging.nats_client import get_nc
from api.services.messaging.streams import realtime_user_subject
from api.services.realtime.frame_limiter import FrameLimiter

log = structlog.get_logger(__name__)

# Below the typical proxy idle timeout (60 s); the client watchdog (45 s) treats two missed
# heartbeats as a dead connection.
SSE_HEARTBEAT_SECONDS = 20.0


class EventBus:
    async def subscribe(self, user_id: int | str) -> AsyncIterator[str]:
        """Frames SSE do canal do usuário; heartbeat quando o silêncio estica."""
        nc = get_nc()
        subject = realtime_user_subject(user_id)
        sub = await nc.subscribe(subject)
        log.info("sse_subscribed", user_id=user_id, subject=subject)
        limiter = FrameLimiter(time.monotonic)
        try:
            while True:
                wait = limiter.seconds_until_flush()
                try:
                    msg = await sub.next_msg(
                        timeout=wait if wait is not None else SSE_HEARTBEAT_SECONDS
                    )
                except NatsTimeoutError:
                    frames = limiter.flush()
                    # Only a real idle timeout (nothing held) is a heartbeat.
                    for frame in frames or ([": heartbeat\n\n"] if wait is None else []):
                        yield frame
                    continue
                for frame in limiter.offer(msg.data):
                    yield frame
                for frame in limiter.flush():
                    yield frame
        finally:
            try:
                await sub.unsubscribe()
            except Exception as exc:
                log.warning("sse_unsubscribe_failed", user_id=user_id, error=str(exc))
            log.info("sse_unsubscribed", user_id=user_id)

    async def publish(self, user_id: int | str, event: dict[str, Any]) -> None:
        await get_nc().publish(realtime_user_subject(user_id), orjson.dumps(event))

    async def publish_many(self, user_ids: Iterable[int | str], event: dict[str, Any]) -> None:
        body = orjson.dumps(event)
        nc = get_nc()
        for user_id in user_ids:
            await nc.publish(realtime_user_subject(user_id), body)


event_bus = EventBus()
