"""Event-driven cache invalidation using NATS as the bus.

Pattern: writer publishes invalidation event after committing the source-of-truth
mutation; subscribers in every app instance wipe affected Valkey keys.

This decouples cache lifetime from TTL. TTL is the safety net (5–60s); the event
is the primary mechanism for fresh data.
"""

from __future__ import annotations

import nats
from nats.aio.msg import Msg

import valkey.asyncio as valkey


# ---------- Producer side -------------------------------------------------
async def update_user_role(
    nc: nats.NATS,
    conn,
    user_id: int,
    new_role: str,
) -> None:
    async with conn.transaction():
        await conn.execute("UPDATE users SET role=$1 WHERE id=$2", new_role, user_id)
    # Publish AFTER commit. Never before — readers may pick the new event then
    # query the old DB state if your replicas lag.
    await nc.publish(f"app.auth.invalidate.user.{user_id}", b"")


async def invalidate_org(
    nc: nats.NATS,
    org_id: str,
) -> None:
    """Bulk invalidation when something org-wide changes (e.g., custom_roles updated)."""
    await nc.publish(f"app.auth.invalidate.org.{org_id}", b"")


# ---------- Consumer side (started in lifespan) ---------------------------
class AuthInvalidator:
    """Subscribes to invalidation subjects and wipes corresponding Valkey keys."""

    def __init__(self, valkey_client: valkey.Valkey, nc: nats.NATS) -> None:
        self.client = valkey_client
        self.nc = nc

    async def start(self) -> None:
        await self.nc.subscribe(
            "app.auth.invalidate.user.>",
            cb=self._on_user_invalidate,
            queue="auth-invalidator",
        )
        await self.nc.subscribe(
            "app.auth.invalidate.org.>",
            cb=self._on_org_invalidate,
            queue="auth-invalidator",
        )

    async def _on_user_invalidate(self, msg: Msg) -> None:
        user_id = msg.subject.rsplit(".", 1)[-1]
        async with self.client.pipeline(transaction=False) as p:
            p.delete(f"cache:auth:user:{user_id}")
            p.delete(f"cache:auth:user:{user_id}:perms")
            p.delete(f"cache:user:{user_id}:settings")
            await p.execute()

    async def _on_org_invalidate(self, msg: Msg) -> None:
        org_id = msg.subject.rsplit(".", 1)[-1]
        # Versioned key bump — invalidates all `cache:org:<id>:v<n>:*` reads
        await self.client.incr(f"cache:org:{org_id}:version")


# ---------- Without NATS (TTL-only fallback) -----------------------------
# When the app has no NATS, document SLO as: "role-change propagates within
# ttl_seconds across all workers". For shorter propagation without a broker,
# Valkey's own Pub/Sub can serve as in-cluster fan-out:
#
#   await client.publish("invalidate:user:42", b"")
#   pubsub = client.pubsub()
#   await pubsub.psubscribe("invalidate:*")
#
# Same caveats as NATS core: at-most-once, no buffering. Acceptable for cache
# invalidation specifically because TTL is the safety net.
