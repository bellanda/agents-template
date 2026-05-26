---
name: valkey-cache
description: Valkey (Redis OSS fork) cache patterns with valkey-py — cache-aside, sliding window rate limit, atomic counters, pipeline batching, event-driven invalidation. Use when designing read caches, throttle counters, hot KV state, or any low-latency lookup pattern. Connection is UDS-only.
---

# Valkey — Cache Patterns with Python (valkey-py)

Covers the canonical cache and counter patterns with `valkey-py` async client over a Unix Domain Socket. Connection convention: `unix:///run/valkey/valkey.sock` mounted from a shared Docker volume. TCP is **disabled** at the server level (`--port 0 --unixsocket ...`).

**Boundary rule (memorize):** messaging → NATS, cache → Valkey. Never confuse the two. Pub/Sub via Valkey is allowed only as in-process invalidation fan-out where NATS is unavailable; for cross-service events, use NATS.

## 1. Connection (always async, always UDS)

```python
import valkey.asyncio as valkey

client = valkey.Valkey.from_url(
    "unix:///run/valkey/valkey.sock",
    decode_responses=False,         # keep bytes — pair with orjson for JSON values
    socket_keepalive=True,
)
await client.ping()
```

Critical:

- One client instance per process. valkey-py is connection-pool-backed and async-safe.
- `decode_responses=False` means GET returns `bytes` — convert at boundary with `orjson.loads(b)`. Don't enable string decode globally; it kills binary-safe values.
- Close on shutdown: `await client.aclose()`.

## 2. Cache-Aside (the 95% case)

**What it solves:** read-heavy data that's expensive to compute but rarely changes. Read from cache; on miss, load from source and populate cache.

```python
import orjson
from valkey.asyncio import Valkey

CACHE_TTL = 300

async def get_org_config(client: Valkey, org_id: str) -> dict:
    key = f"cache:org:{org_id}:config"
    raw = await client.get(key)
    if raw is not None:
        return orjson.loads(raw)
    config = await _load_org_config_from_db(org_id)   # cold path
    await client.set(key, orjson.dumps(config), ex=CACHE_TTL)
    return config
```

Critical:

- `ex=` sets TTL in seconds. Always set one. A cache without TTL is a memory leak waiting to happen.
- Use `orjson.dumps` / `orjson.loads` for value serialization. Never `json` (10× slower, breaks on `datetime`, `UUID`).
- Keep the source-of-truth load path callable independently — useful for warm-up scripts and tests.

## 3. Pipeline Batching

**What it solves:** N independent commands in a single network roundtrip. With UDS the roundtrip is ~50–80 μs; pipelining 10 ops in 1 roundtrip turns 800 μs into 100 μs.

```python
async with client.pipeline(transaction=False) as p:
    for user_id in user_ids:
        p.get(f"cache:auth:user:{user_id}")
    raw_values = await p.execute()
results = [orjson.loads(v) if v else None for v in raw_values]
```

Critical:

- `transaction=False` — pipeline batches commands without `MULTI/EXEC`. Use `transaction=True` only when you need atomicity across the batch.
- Pipeline does NOT short-circuit on errors mid-batch; check each result.

## 4. Counters & Atomic Ops (INCR / DECR / EXPIRE)

**What it solves:** rate counters, view counts, anything safe under concurrent writes.

```python
async def increment_view(client: Valkey, post_id: str) -> int:
    key = f"counter:post:{post_id}:views"
    new_value = await client.incr(key)
    if new_value == 1:
        await client.expire(key, 3600)        # only set TTL on first hit
    return new_value
```

Critical:

- `INCR` is atomic — multiple clients incrementing the same key never lose updates.
- Only set `EXPIRE` on the first hit (when `INCR` returns 1) — re-applying TTL every hit reduces accuracy under load. If the key was removed by eviction, the next `INCR` returns 1 and you get a fresh TTL.

## 5. Sliding Window Rate Limit (sorted set)

**What it solves:** rate limit `N` requests per `W` seconds per identity. More accurate than fixed-window counters.

```python
import time
from valkey.asyncio import Valkey

async def is_rate_limited(client: Valkey, identity: str, limit: int, window_s: int) -> bool:
    key = f"ratelimit:{identity}"
    now_ms = int(time.time() * 1000)
    window_start = now_ms - window_s * 1000

    async with client.pipeline(transaction=True) as p:
        p.zremrangebyscore(key, 0, window_start)        # drop old hits
        p.zadd(key, {f"{now_ms}-{id(time)}": now_ms})    # record this hit
        p.zcard(key)                                     # count remaining
        p.expire(key, window_s + 1)                      # garbage collect
        _, _, count, _ = await p.execute()

    return count > limit
```

Critical:

- `transaction=True` ensures the four ops are atomic — no race where a hit slips through during cleanup.
- Member must be unique per insert (use `now_ms-id(time)` or `uuid4`) — same-score members would collide and overwrite.
- Prefer **nginx `limit_req_zone`** for HTTP rate limit; this pattern is for **business-level throttles** (e.g., "max 10 SMS sends per user per minute") that nginx can't see.

## 6. Event-Driven Invalidation (preferred over short TTL)

**What it solves:** keep cache fresh without aggressive TTLs. When the source mutates, publish an invalidation event; consumers wipe affected keys.

Pattern (uses NATS for the event bus, Valkey for the cache):

```python
# producer side — wherever the source mutates
async def update_user_role(conn, user_id: int, role: str) -> None:
    await conn.execute("UPDATE users SET role=$1 WHERE id=$2", role, user_id)
    await nats.publish(f"app.auth.invalidate.user.{user_id}", b"")

# consumer side — single subscriber per app instance, runs in lifespan
async def auth_invalidator(client: Valkey, nats):
    async def handler(msg):
        user_id = msg.subject.rsplit(".", 1)[-1]
        async with client.pipeline(transaction=False) as p:
            p.delete(f"cache:auth:user:{user_id}")
            p.delete(f"cache:auth:user:{user_id}:perms")
            await p.execute()
    await nats.subscribe("app.auth.invalidate.user.>", cb=handler)
```

Critical:

- TTL is the **fallback safety net** (e.g., 5 min). Event-driven invalidation is the **primary** mechanism for fresh data.
- Hash the cached token in the cache key — never use the raw JWT as a key prefix.

## 7. Versioned Keys (cache-busting without DELETE)

**What it solves:** invalidating a logical group of keys (e.g., "all org X caches") without iterating SCAN.

```python
async def get_cached_org_listing(client: Valkey, org_id: str, page: int) -> list:
    version = await client.get(f"cache:org:{org_id}:version") or b"0"
    key = f"cache:org:{org_id}:v{version.decode()}:listing:p{page}"
    raw = await client.get(key)
    if raw:
        return orjson.loads(raw)
    listing = await _load_listing_from_db(org_id, page)
    await client.set(key, orjson.dumps(listing), ex=3600)
    return listing

async def invalidate_org_cache(client: Valkey, org_id: str) -> None:
    await client.incr(f"cache:org:{org_id}:version")
    # all old keys (cache:org:X:v3:*) become unreachable; evicted by allkeys-lru.
```

Critical:

- INCR on the version key is O(1); next reads compute new key prefix; old entries age out via LRU.
- Avoids `KEYS *` and `SCAN` over potentially millions of keys.

## 8. SCAN (never KEYS)

**What it solves:** iterate over keys matching a pattern in production-safe chunks.

```python
async def delete_pattern(client: Valkey, pattern: str) -> int:
    deleted = 0
    async for key in client.scan_iter(match=pattern, count=500):
        deleted += await client.delete(key)
    return deleted
```

Critical:

- `KEYS *` blocks the server for the duration of the scan — banned in production.
- `scan_iter` uses cursor-based iteration, non-blocking. `count=500` is a hint, not a hard batch size.

## 9. Lua Scripts (compare-and-set, atomic check)

**What it solves:** read-modify-write semantics that must be atomic, when MULTI/EXEC is insufficient.

```python
INCR_IF_BELOW_LIMIT = """
local count = tonumber(redis.call('GET', KEYS[1]) or '0')
if count >= tonumber(ARGV[1]) then return 0 end
redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[2])
return 1
"""

async def try_consume_quota(client: Valkey, key: str, limit: int, ttl: int) -> bool:
    result = await client.eval(INCR_IF_BELOW_LIMIT, 1, key, limit, ttl)
    return bool(result)
```

Critical:

- `redis.call(...)` inside Lua, not `client.call(...)` — Lua executes server-side.
- Keep scripts short. Lua blocks the single-threaded event loop of Valkey while running.
- Use `client.script_load()` + `client.evalsha()` if you call the same script repeatedly.

## 10. Key Naming Convention

```
<purpose>:<domain>:<entity>:<id>[:<facet>]

cache:auth:user:42                 ← cached auth_context for user id 42
cache:org:abc-uuid:roles           ← roles for org abc-uuid
cache:event:evt-uuid               ← event row JSON
counter:post:42:views              ← view counter
ratelimit:ip:1.2.3.4               ← sliding window per IP
ratelimit:user:42:sms              ← business throttle: SMS per user
flag:global:maintenance            ← feature flag
lock:job:nightly-aggregation       ← simple distributed lock with NX+EX
```

Critical:

- Always namespace by purpose prefix (`cache:`, `counter:`, `ratelimit:`, `flag:`, `lock:`). Lets you SCAN/MONITOR by purpose and apply different eviction policies later.
- Multi-tenant apps add an app prefix: `myapp:cache:org:...`. Single-app deployments can omit.

## 11. Default TTLs by Category

| Category                 | Typical TTL | Reason                                                  |
| ------------------------ | ----------- | ------------------------------------------------------- |
| auth_context             | 60 s        | Short to limit role-change propagation delay            |
| org_config / settings    | 300 s       | Mid-frequency mutation, paired with event invalidation  |
| listings / dashboards    | 3600 s      | Heavy read, computed nightly or on demand               |
| feature flags            | 30 s        | Fast rollout/rollback                                   |
| static lookup tables     | 86400 s     | Reference data — usually invalidated explicitly         |
| rate-limit windows       | window + 1s | Always TTL = window length + 1s buffer                  |

## 12. What NOT to do

- **No `KEYS *`** in hot path. Use SCAN.
- **No `decode_responses=True`** globally. Keep bytes; decode at boundary with orjson.
- **No long Lua scripts** (>1ms). They block the server's main loop.
- **No raw JWT or PII as key segments.** Hash with SHA-256 truncated to 32 chars: `key = f"cache:auth:tok:{hashlib.sha256(token).hexdigest()[:32]}"`.
- **No Valkey for messaging** (Pub/Sub is fire-and-forget like NATS core, but you already have NATS — keep boundaries clean).
- **No JetStream-replacement attempts.** Persistent durable streams stay in NATS JetStream.
- **No cross-service events through Valkey.** That's NATS's job.

## 13. Persistence: AOF everysec (default for cache use)

Server runs with `--appendonly yes --appendfsync everysec`. Why:

- Reads are unaffected (everything is in RAM regardless of AOF).
- Writes pay ~0 μs because fsync runs in a background thread every second.
- Worst-case data loss = 1 second of writes on hard crash. Acceptable for cache.
- Avoids cold-start where 100% of cache misses hit Postgres simultaneously after restart.

For pure throwaway counters (e.g., view counts where loss is tolerable), an alternative server with `--appendfsync no` is fine but not worth the operational split for typical workloads.

## 14. Eviction: allkeys-lru

`--maxmemory 256mb --maxmemory-policy allkeys-lru` evicts least-recently-used keys when memory is full. Suits cache workloads. Don't use `noeviction` — it makes the server return errors on writes when memory is full, which silently turns into "everyone hits Postgres" in production.

## 15. Connection Patterns Reference

```python
# Lifespan integration
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    await init_valkey()
    yield
    await close_valkey()

# Singleton accessor
_client: valkey.Valkey | None = None

async def init_valkey() -> None:
    global _client
    _client = valkey.Valkey.from_url(
        "unix:///run/valkey/valkey.sock",
        decode_responses=False,
        socket_keepalive=True,
    )
    await _client.ping()

async def close_valkey() -> None:
    if _client:
        await _client.aclose()

def get_valkey() -> valkey.Valkey:
    if _client is None:
        raise RuntimeError("valkey_not_initialized")
    return _client
```

`get_valkey()` is the standard handle used across the app. Don't re-create a client per request — the pool inside the singleton is enough.

## 16. References (working code)

See `references/` directory:

- `cache_aside.py` — full cache-aside example with decorator wrapper.
- `sliding_window_rate_limit.py` — production-grade rate limit with sorted set.
- `invalidation_via_nats.py` — auth invalidation consumer pattern.
- `auth_context_cache.py` — caching FastAPI auth dependency with TTL + invalidation.
