"""Valkey client singleton — UDS-only, async, cache scope.

Boundary contract: cache → Valkey, messaging → NATS.

Auth: docker valkey runs with `--requirepass ${VALKEY_PASSWORD}`, so the client
sends AUTH when the password is set. A native host-dev Valkey usually runs
passwordless; if AUTH is sent but the server has no `requirepass`, `_connect`
detects the rejection and retries without AUTH. A real password mismatch
(WRONGPASS) is not swallowed.

Timeouts (audit 2026-11-13 core-performance-03): valkey-py defaults to
`socket_timeout=None` and an unbounded pool, so a Valkey that stops answering (fork for a
snapshot, disk stall, OOM) froze EVERY authenticated request: the permission cache is read
on the hot path and its "fail-open to the database" only covered Valkey RETURNING an error,
not Valkey going silent. Now every command gives up after SOCKET_TIMEOUT_SECONDS (UDS answers
in microseconds, so this only trips on a real stall), the pool is capped, and callers that
treat the cache as optional fall back to Postgres. Blocking commands (BLPOP, XREAD BLOCK) are
NOT allowed on this shared client; give them a dedicated client with their own timeout.
`PubSub.get_message(timeout=...)` is fine: the explicit timeout wins over the socket one.

Lazy reconnect: `init_valkey` keeps the client even when the boot ping fails (Valkey still
starting during a deploy), so the worker recovers by itself when Valkey comes up instead of
running without cache until the next worker recycle.
"""

import functools
from collections.abc import Awaitable, Callable
from typing import Final

import structlog
import valkey.asyncio as valkey
from valkey.exceptions import ValkeyError

from config.cache import cache_config

log = structlog.get_logger(__name__)

SOCKET_TIMEOUT_SECONDS: Final = 0.25
SOCKET_CONNECT_TIMEOUT_SECONDS: Final = 0.25
HEALTH_CHECK_INTERVAL_SECONDS: Final = 30
MAX_CONNECTIONS: Final = 64

# What "Valkey is unavailable" looks like to a caller: server/protocol error, socket error
# (OSError covers a missing UDS and TimeoutError), or the client never created.
VALKEY_UNAVAILABLE: Final = (ValkeyError, OSError, RuntimeError)

_client: valkey.Valkey | None = None

# Valkey replies with this when AUTH is sent but no `requirepass` is configured.
_NO_SERVER_PASSWORD_MARKERS = ("without any password configured", "no password is set")


def _build_client(*, with_password: bool) -> valkey.Valkey:
    kwargs: dict = {
        "decode_responses": False,
        "socket_timeout": SOCKET_TIMEOUT_SECONDS,
        "socket_connect_timeout": SOCKET_CONNECT_TIMEOUT_SECONDS,
        "health_check_interval": HEALTH_CHECK_INTERVAL_SECONDS,
        "max_connections": MAX_CONNECTIONS,
        "retry_on_timeout": False,
    }
    if with_password:
        kwargs["password"] = cache_config.VALKEY_PASSWORD
    return valkey.Valkey.from_url(f"unix://{cache_config.VALKEY_SOCK_PATH}", **kwargs)


async def _connect(*, with_password: bool) -> valkey.Valkey:
    client = _build_client(with_password=with_password)
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
    """Create the client; re-raises when the boot ping fails but KEEPS the client for lazy reconnect."""
    global _client
    if _client is not None:
        return
    with_password = bool(cache_config.VALKEY_PASSWORD)
    try:
        _client = await _connect(with_password=with_password)
    except (ValkeyError, OSError):
        _client = _build_client(with_password=with_password)
        raise


async def close_valkey() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_valkey() -> valkey.Valkey:
    if _client is None:
        raise RuntimeError("valkey_not_initialized")
    return _client


def valkey_fail_open(default: object = None):
    """Decorator for optional-cache helpers: Valkey unavailable → log + return `default`.

    Policy (audit 2026-11-13 core-security-03): a Valkey outage must never turn into a 500 on
    every authenticated request or into a login that cannot finish. Throttle counters and the
    session denylist are best-effort controls; the access token still expires by `exp` (minutes)
    and the refresh family is revoked in Postgres, so degrading open for a few seconds is the
    smaller harm. Domain exceptions (RateLimitError, ...) are not in VALKEY_UNAVAILABLE and pass.
    """

    def decorate(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except VALKEY_UNAVAILABLE:
                log.warning(
                    "valkey_unavailable_fail_open", operation=func.__qualname__, exc_info=True
                )
                return default

        return wrapper

    return decorate
