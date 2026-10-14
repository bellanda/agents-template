"""Valkey client singleton — UDS-only, async, cache scope.

Boundary contract: cache → Valkey, messaging → NATS.

Auth: docker valkey runs with `--requirepass ${VALKEY_PASSWORD}`, so the client
sends AUTH when the password is set. A native host-dev Valkey usually runs
passwordless; if AUTH is sent but the server has no `requirepass`, `_connect`
detects the rejection and retries without AUTH. A real password mismatch
(WRONGPASS) is not swallowed.
"""

import structlog
import valkey.asyncio as valkey
from valkey.exceptions import ValkeyError

from config.cache import cache_config

log = structlog.get_logger(__name__)

_client: valkey.Valkey | None = None

# Valkey replies with this when AUTH is sent but no `requirepass` is configured.
_NO_SERVER_PASSWORD_MARKERS = ("without any password configured", "no password is set")


async def _connect(*, with_password: bool) -> valkey.Valkey:
    kwargs: dict = {"decode_responses": False}
    if with_password:
        kwargs["password"] = cache_config.VALKEY_PASSWORD
    client = valkey.Valkey.from_url(f"unix://{cache_config.VALKEY_SOCK_PATH}", **kwargs)
    try:
        await client.ping()
    except ValkeyError as exc:
        # A filled VALKEY_PASSWORD (kept for Docker, where --requirepass is
        # mandatory) makes the client send AUTH; a native host-dev Valkey running
        # passwordless rejects it. Retry without AUTH. WRONGPASS is not matched here.
        message = str(exc).lower()
        if with_password and any(m in message for m in _NO_SERVER_PASSWORD_MARKERS):
            await client.aclose()
            log.warning("valkey_auth_skipped_passwordless_server")
            return await _connect(with_password=False)
        raise
    return client


async def init_valkey() -> None:
    global _client
    if _client is not None:
        return
    _client = await _connect(with_password=bool(cache_config.VALKEY_PASSWORD))


async def close_valkey() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_valkey() -> valkey.Valkey:
    if _client is None:
        raise RuntimeError("valkey_not_initialized")
    return _client
