"""`POST /client-logs`: browser error becomes a `client_error` line in the backend log.

Optional identity (annotates `user_id` only with an Authorization header), per-IP cap in events
with silent drop, and schema limits on a public route. The route is mounted on a bare FastAPI app
(the template conftest has no HTTP client fixture and the full app boots NATS/Postgres in its
lifespan). The service `log` is swapped for a recorder: structlog caches loggers on first use,
so `capture_logs` would not see it.
"""

import httpx
import pytest
from fastapi import FastAPI

from api.routes.observability import client_logs_router
from api.services.observability import client_logs as client_logs_service

ENDPOINT = "/api/v1/client-logs"


class RecordingLog:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def warning(self, event: str, **fields) -> None:
        self.events.append((event, fields))


def _event(**overrides) -> dict:
    return {
        "kind": "api_error",
        "title": "Não foi possível salvar a configuração",
        "message": "Configuração inválida.",
        "route": "/agents/config",
        "request_id": "req-123",
        "status": 409,
        "occurred_at": "2026-10-22T12:00:00Z",
        **overrides,
    }


@pytest.fixture
async def client():
    app = FastAPI()
    app.include_router(client_logs_router, prefix="/api/v1")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture
def recorded(monkeypatch) -> RecordingLog:
    recorder = RecordingLog()
    monkeypatch.setattr(client_logs_service, "log", recorder)
    return recorder


async def test_client_logs_write_one_line_per_event_with_user_when_authenticated(client, recorded):
    anonymous = await client.post(ENDPOINT, json={"events": [_event()]})
    assert anonymous.status_code == 204

    logged_in = await client.post(
        ENDPOINT,
        json={"events": [_event(), _event(kind="unhandled", request_id=None)]},
        headers={"Authorization": "Bearer user-42"},
    )
    assert logged_in.status_code == 204

    lines = [fields for event, fields in recorded.events if event == "client_error"]
    assert len(lines) == 3
    assert lines[0]["user_id"] is None
    assert lines[0]["source"] == "frontend"
    assert lines[0]["client_request_id"] == "req-123"
    assert lines[1]["user_id"] == "user-42"
    assert lines[2]["kind"] == "unhandled"


async def test_client_logs_drop_silently_over_ip_limit_and_reject_oversized_batches(
    client, recorded, monkeypatch
):
    async def over_limit(ip: str, event_count: int) -> bool:
        return False

    oversized = await client.post(ENDPOINT, json={"events": [_event()] * 21})
    assert oversized.status_code == 422
    too_long = await client.post(ENDPOINT, json={"events": [_event(message="x" * 501)]})
    assert too_long.status_code == 422

    monkeypatch.setattr("api.routes.observability.client_logs.is_client_log_allowed", over_limit)
    dropped = await client.post(ENDPOINT, json={"events": [_event()]})
    assert dropped.status_code == 204
    assert recorded.events == []
