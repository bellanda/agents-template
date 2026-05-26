"""Cached FastAPI auth dependency — placeholder for the future wave.

This is the canonical pattern for caching the auth_context that today is
re-computed (with N SELECTs) on every authenticated request. NOT applied in
the current refactor wave — kept here as the target for the isolated auth
cache wave.

Pattern: hash the token to derive the cache key (never use the raw JWT as a key
prefix). On hit, deserialize and return. On miss, run the original validator,
cache, return. Invalidation on logout / role change deletes the key directly.
"""

from __future__ import annotations

import hashlib

import orjson
from asyncpg import Connection
from fastapi import Depends, Request

# Stubs — replace with real imports in your project
# from api.services.cache.valkey_client import get_valkey
# from config.cache import cache_config
# from config.database import get_conn
# from api.services.auth.permission_service import _validate_authentication_only, _extract_token


def _cache_key(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    return f"cache:auth:tok:{digest}"


async def get_auth_context_cached(
    request: Request,
    conn: Connection = Depends(...),  # Depends(get_conn)
) -> dict:
    token = _extract_token(request)
    client = get_valkey()
    cache_key = _cache_key(token)

    raw = await client.get(cache_key)
    if raw is not None:
        return orjson.loads(raw)

    ctx = await _validate_authentication_only(conn, token)
    await client.set(
        cache_key,
        orjson.dumps(ctx),
        ex=60,  # cache_config.AUTH_CONTEXT_TTL_SECONDS
    )
    # Also index by user_id for fast invalidation
    await client.sadd(f"cache:auth:user:{ctx['user_id']}:tokens", cache_key)
    await client.expire(f"cache:auth:user:{ctx['user_id']}:tokens", 86400)
    return ctx


async def invalidate_user_auth(client, user_id: int) -> None:
    """Wipe all cached auth_context entries for a user — used on logout, role change."""
    set_key = f"cache:auth:user:{user_id}:tokens"
    token_keys = await client.smembers(set_key)
    if not token_keys:
        return
    async with client.pipeline(transaction=False) as p:
        for k in token_keys:
            p.delete(k)
        p.delete(set_key)
        await p.execute()


# Stubs to keep the file importable in isolation
def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("access_token", "")


async def _validate_authentication_only(conn: Connection, token: str) -> dict:
    raise NotImplementedError("import from permission_service")


def get_valkey():
    raise NotImplementedError("import from valkey_client")
