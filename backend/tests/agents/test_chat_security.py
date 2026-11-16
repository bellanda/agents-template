"""Chat endpoint security (audit 2026-11-13: skills-backend-01, core-ai-02; port of the
optimuslar/kailos fixes).

- the legacy ``files`` (server paths sent by the client) channel is gone: a path is never read;
- an attachment ``parts`` URL is read only when it is the caller's own (or public) upload;
- ``session_id`` is client-supplied and the checkpoint is keyed by thread_id alone, so continuing
  another user's thread is refused (403);
- an unhandled error is a generic 500 (no exception text in the body).
"""

from pathlib import Path

import pytest

from api.models.agents.history import ChatHistoryThread
from api.models.uploads.upload_jsonb import UploadVisibility
from api.repositories.agents.chat_history import save_chat
from api.routes.agents import chat as chat_module
from api.routes.agents.chat import ChatRequest
from api.services.uploads.upload_access_service import (
    authorize_upload_path,
    resolve_upload_path,
)
from config.api import api_config

API = "/api/v1/agents"
ALICE = {"x-user-id": "alice"}
BOB = {"x-user-id": "bob"}
CHAT = f"{API}/chat/completions"
MODEL = "echo-agent"


@pytest.fixture
def captured_query(monkeypatch, fake_registry):
    """Replace the agent runner by a recorder; returns the list of queries the model would see."""
    fake_registry({MODEL: {"name": "Echo", "capabilities": {}}})
    seen: list = []

    async def _call(*, query, **_):
        seen.append(query)
        return "ok"

    monkeypatch.setattr(chat_module, "call_agent_async", _call)
    return seen


def _body(**extra):
    return {"messages": [{"role": "user", "content": "hi"}], "model": MODEL, **extra}


def _parts_body(url: str):
    return {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "parts": [
                    {"type": "text", "text": "leia"},
                    {"type": "file", "url": url, "mediaType": "text/plain", "filename": "a.txt"},
                ],
            }
        ],
    }


def test_chat_request_has_no_server_path_or_identity_field():
    assert "files" not in ChatRequest.model_fields
    assert "user" not in ChatRequest.model_fields


class TestServerPathsAreNeverRead:
    async def test_files_field_with_etc_passwd_is_ignored(self, client, captured_query):
        res = await client.post(CHAT, headers=ALICE, json=_body(files=["/etc/passwd"]))
        assert res.status_code == 200, res.text
        assert captured_query == ["hi"]  # nothing from /etc/passwd reached the model

    async def test_absolute_path_in_parts_url_is_not_read(self, client, captured_query):
        res = await client.post(CHAT, headers=ALICE, json=_parts_body("/etc/passwd"))
        assert res.status_code == 200, res.text
        assert "root:" not in str(captured_query)

    async def test_traversal_url_is_not_read(self, client, captured_query):
        url = f"{api_config.UPLOADS_HTTP_PREFIX}/../../../../etc/passwd"
        res = await client.post(CHAT, headers=ALICE, json=_parts_body(url))
        assert res.status_code == 200, res.text
        assert "root:" not in str(captured_query)

    def test_resolver_rejects_outside_and_traversal(self):
        assert resolve_upload_path("/etc/passwd") is None
        assert resolve_upload_path(f"{api_config.UPLOADS_HTTP_PREFIX}/../../etc/passwd") is None
        assert resolve_upload_path("") is None


class TestUploadOwnership:
    async def test_owner_attachment_reaches_the_model(self, client, captured_query, seed_upload):
        url = await seed_upload("alice", "mine.txt", "PLANILHA-DA-ALICE")
        res = await client.post(CHAT, headers=ALICE, json=_parts_body(url))
        assert res.status_code == 200, res.text
        assert "PLANILHA-DA-ALICE" in str(captured_query)

    async def test_other_users_private_attachment_is_dropped(
        self, client, captured_query, seed_upload
    ):
        url = await seed_upload("alice", "secret.txt", "SEGREDO-DA-ALICE")
        res = await client.post(CHAT, headers=BOB, json=_parts_body(url))
        assert res.status_code == 200, res.text
        assert "SEGREDO-DA-ALICE" not in str(captured_query)

    async def test_public_attachment_is_readable_by_anyone(
        self, client, captured_query, seed_upload
    ):
        url = await seed_upload("alice", "pub.txt", "PUBLICO", visibility=UploadVisibility.PUBLIC)
        await client.post(CHAT, headers=BOB, json=_parts_body(url))
        assert "PUBLICO" in str(captured_query)

    async def test_untracked_contained_file_is_dropped(self, db_conn):
        base = Path(api_config.UPLOADS_DIR).resolve()
        ghost = base / "ghost-no-row.txt"
        ghost.write_text("sem linha em user_uploads")
        try:
            assert await authorize_upload_path(ghost, db_conn, "alice") is None
        finally:
            ghost.unlink(missing_ok=True)


class TestThreadOwnership:
    async def _seed_thread_of_alice(self, db_conn) -> str:
        thread_id = "thread-owned-by-alice"
        await save_chat(
            db_conn,
            ChatHistoryThread(
                thread_id=thread_id,
                user_id="alice",
                agent_id=MODEL,
                messages=[{"role": "user", "content": "dados do cliente X"}],
                preview="dados do cliente X",
            ),
        )
        return thread_id

    async def test_other_user_cannot_continue_the_thread(self, client, db_conn, captured_query):
        thread_id = await self._seed_thread_of_alice(db_conn)
        res = await client.post(CHAT, headers=BOB, json=_body(session_id=thread_id))
        assert res.status_code == 403, res.text
        assert captured_query == []  # the agent was never invoked

    async def test_owner_can_continue_the_thread(self, client, db_conn, captured_query):
        thread_id = await self._seed_thread_of_alice(db_conn)
        res = await client.post(CHAT, headers=ALICE, json=_body(session_id=thread_id))
        assert res.status_code == 200, res.text


async def test_unhandled_error_is_a_generic_500(client, monkeypatch, fake_registry):
    fake_registry({MODEL: {"name": "Boom", "capabilities": {}}})
    secret = "SQL fragment password=hunter2 at /app/.env"

    async def _boom(**_):
        raise RuntimeError(secret)

    monkeypatch.setattr(chat_module, "call_agent_async", _boom)
    res = await client.post(CHAT, headers=ALICE, json=_body())
    assert res.status_code == 500
    assert res.json()["detail"] == "Internal error"
    assert "hunter2" not in res.text
