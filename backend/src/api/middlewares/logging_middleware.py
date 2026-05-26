"""ASGI logging middleware.

Reads X-Request-ID from the incoming request (nginx/Cloudflare generates it),
binds it as a structlog contextvar so every log line emitted during the request
inherits it, and emits one summary log line on response with
method/path/status/duration_ms.

Pure ASGI — does not inherit BaseHTTPMiddleware to avoid breaking streaming
responses / SSE / WebSocket upgrade.
"""

import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.core.logging import bind_request_id, clear_request_id, get_logger

REQUEST_ID_HEADER = b"x-request-id"
RESPONSE_HEADER_NAME = b"x-request-id"

# Paths that flood the log with noise without operational value (probes, docs).
# Logged only when status >= 400 (so real failures still surface).
SILENT_PATHS = frozenset(
    {
        "/",
        "/health",
        "/healthz",
        "/api/v1/docs",
        "/api/v1/redoc",
        "/api/v1/openapi.json",
        "/favicon.ico",
    }
)
ERROR_STATUS_THRESHOLD = 400


class LoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.log = get_logger("api.http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request_id = _extract_request_id(scope.get("headers") or [])
        bind_request_id(request_id)

        start_ns = time.perf_counter_ns()
        status_holder: dict[str, int] = {"status": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = int(message.get("status", 0))
                headers = list(message.get("headers") or [])
                headers.append((RESPONSE_HEADER_NAME, request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        path = scope.get("path") or ""

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            self.log.exception(
                "http_request_error",
                method=scope.get("method"),
                path=path,
                duration_ms=round(duration_ms, 2),
                client_ip=_client_ip(scope),
            )
            raise
        else:
            status = status_holder["status"]
            # Silence noise paths on success; always surface errors regardless of path.
            if path in SILENT_PATHS and status < ERROR_STATUS_THRESHOLD:
                return
            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            level = "warning" if status >= ERROR_STATUS_THRESHOLD else "info"
            getattr(self.log, level)(
                "http_request",
                method=scope.get("method"),
                path=path,
                status=status,
                duration_ms=round(duration_ms, 2),
                client_ip=_client_ip(scope),
            )
        finally:
            clear_request_id()


def _extract_request_id(headers: list[tuple[bytes, bytes]]) -> str:
    for name, value in headers:
        if name.lower() == REQUEST_ID_HEADER:
            decoded = value.decode("latin-1").strip()
            if decoded:
                return decoded
    return uuid.uuid4().hex


def _client_ip(scope: Scope) -> str:
    # Prefer X-Real-IP set by the reverse proxy; fall back to the socket peer.
    for name, value in scope.get("headers") or []:
        if name.lower() == b"x-real-ip":
            ip = value.decode("latin-1").strip()
            if ip:
                return ip
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"
