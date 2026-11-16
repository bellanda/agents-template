"""Generic `entity.changed` event (fleet standard, audit 2026-11-13 core-spa-05).

Wire shape: `{"type": "entity.changed", "payload": {"entity": "approval", "org_id": "...",
"ids": ["..."]}}`. It is a SIGNAL, never content: the client invalidates the queries it owns for
that entity and the REST API (which checks permission) serves the data. `ids` is an optional
hint; clients may ignore it, and the per-connection `FrameLimiter` merges bursts of the same
(entity, org) into the latest frame.

WHEN to emit: after the COMMIT of any write to an entity that OTHER users, a webhook or a routine
look at (an approval raised by a seller, a kit handed out by another operator, a work order moved
by another mechanic). Do not emit for the actor's own screen: the mutation already invalidates it
(pass the actor in `exclude_user_id`).

RECIPIENTS are decided here, not by the route that opens the stream: the list must be the same
rule the REST endpoint applies (users holding the permission that reads that entity). The helper
takes the final list, so each app resolves it with its own permission model.

Best-effort: a lost frame only delays the other screen until the next event / reconnect resync,
and the write is already committed, so this never raises.
"""

from collections.abc import Iterable
from typing import Final
from uuid import UUID

import structlog

from api.services.realtime.event_bus import event_bus

log = structlog.get_logger(__name__)

EVENT_ENTITY_CHANGED: Final = "entity.changed"


def entity_changed_event(
    entity: str, org_id: UUID | str, ids: Iterable[UUID | int | str] | None = None
) -> dict:
    payload: dict = {"entity": entity, "org_id": str(org_id)}
    if ids is not None:
        payload["ids"] = [str(item) for item in ids]
    return {"type": EVENT_ENTITY_CHANGED, "payload": payload}


async def publish_entity_changed(
    user_ids: Iterable[int | str],
    entity: str,
    org_id: UUID | str,
    ids: Iterable[UUID | int | str] | None = None,
    *,
    exclude_user_id: int | str | None = None,
) -> None:
    """Tell `user_ids` (minus the actor) that `entity` changed in `org_id`. Call AFTER COMMIT."""
    recipients = [user_id for user_id in user_ids if user_id != exclude_user_id]
    if not recipients:
        return
    try:
        await event_bus.publish_many(recipients, entity_changed_event(entity, org_id, ids))
    except Exception:
        log.warning(
            "entity_changed_publish_failed", entity=entity, org_id=str(org_id), exc_info=True
        )
