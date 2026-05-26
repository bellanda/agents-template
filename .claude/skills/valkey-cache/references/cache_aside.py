"""Cache-aside pattern with decorator wrapper.

Use case: read-heavy DB query that's expensive but rarely changes.
Pattern: GET cache; on miss, load from source; SET with TTL; return.
"""

from __future__ import annotations

import functools
import hashlib
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

import orjson
import valkey.asyncio as valkey

P = ParamSpec("P")
T = TypeVar("T")


def cache_aside(
    *,
    key_template: str,
    ttl_seconds: int,
    client_factory: Callable[[], valkey.Valkey],
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorate an async loader. Cache key derives from kwargs via `key_template.format(**kwargs)`.

    Example:
        @cache_aside(key_template="cache:org:{org_id}:config", ttl_seconds=300, client_factory=get_valkey)
        async def load_org_config(*, org_id: str) -> dict: ...
    """

    def decorator(loader: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(loader)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            client = client_factory()
            key = key_template.format(**kwargs)
            raw = await client.get(key)
            if raw is not None:
                return orjson.loads(raw)
            value = await loader(*args, **kwargs)
            await client.set(key, orjson.dumps(value), ex=ttl_seconds)
            return value

        return wrapper

    return decorator


# Manual usage (no decorator) — when key derivation is more complex
async def get_user_settings(client: valkey.Valkey, user_id: int) -> dict:
    key = f"cache:user:{user_id}:settings"
    raw = await client.get(key)
    if raw is not None:
        return orjson.loads(raw)
    settings = await _load_user_settings_from_db(user_id)
    await client.set(key, orjson.dumps(settings), ex=300)
    return settings


def hash_key(token: str, prefix: str = "cache:auth:tok") -> str:
    """Hash sensitive values (tokens, emails) before using as key segments."""
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}:{digest}"


async def _load_org_config_from_db(org_id: str) -> dict:
    """Stub — replace with real repository call."""
    raise NotImplementedError


async def _load_user_settings_from_db(user_id: int) -> dict:
    """Stub — replace with real repository call."""
    raise NotImplementedError


# Anti-pattern reference (do not copy):
#
# WRONG: forgot TTL — silent memory leak
#   await client.set(key, value)
#
# WRONG: re-applying TTL every read — refreshes hot keys forever
#   if raw is not None:
#       await client.expire(key, 300)
#       return orjson.loads(raw)
#
# WRONG: json.dumps — slow + breaks on UUID/datetime
#   await client.set(key, json.dumps(value), ex=300)
