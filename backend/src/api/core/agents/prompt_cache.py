"""In-process TTL memo for prompt fragments that live in the DB (tenant instructions).

NOT provider prompt caching. That one is automatic on OpenRouter/GLM (implicit prefix cache,
reported as `cache_read` and billed at `cached_input_price_per_1m`) and only asks one thing of
us: keep the PREFIX stable — static base system prompt first, per-tenant/dynamic text after,
and never inject timestamps or request ids at the top of the prompt. `history_window.py` keeps
older turns stable for the same reason (it masks, it does not rewrite, recent context).

This module avoids one DB round-trip per model call: the tenant-instructions middleware runs
before EVERY model call of a turn (tool loops make several). Per-process only: a save
invalidates the worker that handled it; others converge within
`settings.agents.tenant_config_ttl_seconds`.
"""

import time
from typing import Any

from config.settings import settings


class PromptCache:
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._entries[key] = (time.monotonic() + self._ttl, value)

    def invalidate(self, key: str) -> None:
        self._entries.pop(key, None)


prompt_cache = PromptCache(settings.agents.tenant_config_ttl_seconds)
