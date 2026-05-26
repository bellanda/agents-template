"""Sliding window rate limit using ZADD + ZREMRANGEBYSCORE.

Use case: business-level throttle (per user, per org, per resource) that nginx
limit_req cannot enforce. For HTTP-level rate limit, use nginx zones instead.
"""

from __future__ import annotations

import time
import uuid

import valkey.asyncio as valkey


async def is_rate_limited(
    client: valkey.Valkey,
    *,
    identity: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """Returns (is_limited, current_count_in_window).

    Atomic: drop expired entries, record this hit, count remaining, refresh TTL.
    """
    key = f"ratelimit:{identity}"
    now_ms = int(time.time() * 1000)
    window_start_ms = now_ms - window_seconds * 1000
    member = f"{now_ms}:{uuid.uuid4().hex[:8]}"

    async with client.pipeline(transaction=True) as p:
        p.zremrangebyscore(key, 0, window_start_ms)
        p.zadd(key, {member: now_ms})
        p.zcard(key)
        p.expire(key, window_seconds + 1)
        _, _, count, _ = await p.execute()

    return count > limit, count


async def example_usage(client: valkey.Valkey, user_id: int) -> None:
    limited, count = await is_rate_limited(
        client,
        identity=f"sms:user:{user_id}",
        limit=10,
        window_seconds=60,
    )
    if limited:
        raise RuntimeError(f"sms_throttled count={count}")


# Lua-based variant (single roundtrip, no pipeline overhead)
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)
redis.call('ZADD', key, now_ms, member)
redis.call('PEXPIRE', key, window_ms + 1000)
local count = redis.call('ZCARD', key)
return count > limit and 1 or 0
"""


async def is_rate_limited_lua(
    client: valkey.Valkey,
    *,
    identity: str,
    limit: int,
    window_seconds: int,
) -> bool:
    key = f"ratelimit:{identity}"
    now_ms = int(time.time() * 1000)
    window_ms = window_seconds * 1000
    member = f"{now_ms}:{uuid.uuid4().hex[:8]}"
    result = await client.eval(SLIDING_WINDOW_LUA, 1, key, now_ms, window_ms, limit, member)
    return bool(result)
