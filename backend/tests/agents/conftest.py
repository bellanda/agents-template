"""Fixtures for the chat/agents ROUTE tests (HTTP client + fake registry + upload seeding).

`client` talks to the real FastAPI app over ASGI (lifespan NOT run: no NATS/Valkey/registry
discovery) with both DB dependencies pointed at the per-test transaction connection, so route
code that uses `Depends(get_conn)` or `Depends(get_conn_scope)` sees (and rolls back with) the
test's data. Identity is the template's OPEN stub (`X-User-Id`), valid because tests run with
`logging.app_env: test`.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.models.uploads.upload_jsonb import UploadKind, UploadVisibility
from api.models.uploads.user_upload import UserUpload
from api.repositories.uploads.user_upload_repository import user_upload_repository
from api.services.agents.registry import get_agents_registry
from config.api import api_config
from config.database import db_scope, get_conn, get_conn_scope


@pytest.fixture
async def client(db_conn):
    async def _conn():
        yield db_conn

    app.dependency_overrides[get_conn] = _conn
    app.dependency_overrides[get_conn_scope] = lambda: db_scope(db_conn)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def fake_registry():
    """Install `{model_id: agent_info}` as the registry for one test."""

    def install(registry: dict) -> dict:
        app.dependency_overrides[get_agents_registry] = lambda: registry
        return registry

    yield install
    app.dependency_overrides.pop(get_agents_registry, None)


@pytest.fixture
async def seed_upload(db_conn):
    """Write a real file under UPLOADS_DIR and register its `user_uploads` row. Cleans up."""
    created: list[Path] = []

    async def make(owner: str, name: str, text: str, *, visibility=UploadVisibility.PRIVATE) -> str:
        base = Path(api_config.UPLOADS_DIR).resolve()
        target = base / "users" / owner / "chat" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        created.append(target)
        url = f"{api_config.UPLOADS_HTTP_PREFIX}/users/{owner}/chat/{name}"
        await user_upload_repository.create(
            db_conn,
            UserUpload(
                owner_user_id=owner,
                entity_type="chat_session",
                entity_id="t1",
                kind=UploadKind.ATTACHMENT,
                url=url,
                filename=name,
                mime_type="text/plain",
                visibility=visibility,
            ),
        )
        return url

    yield make
    for path in created:
        path.unlink(missing_ok=True)
