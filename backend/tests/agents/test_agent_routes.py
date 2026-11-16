"""Route-level contract of the template's agent API (audit 2026-11-13 template-gap-08 / -01):
identity fails closed outside local/test, threads are owner-scoped, a streamed chat answer is
produced and persisted WITHOUT holding a pooled DB connection, uploads are owner-tracked and
deduplicated, and agent config (tenant instructions) is isolated per tenant.
"""

import asyncio
import contextlib
import shutil
from pathlib import Path

import pytest

from api.repositories.agents.chat_history import get_chat_messages
from api.services import auth as auth_module
from api.services.agents import streaming
from config.api import api_config
from config.database import get_conn_scope

API = "/api/v1/agents"
ALICE = {"x-user-id": "alice"}
BOB = {"x-user-id": "bob"}
MODEL = "echo-agent"


# --------------------------------------------------------------------------- identity


async def test_identity_stub_fails_closed_outside_local_and_test(client, monkeypatch):
    assert (await client.get(f"{API}/threads", headers=ALICE)).status_code == 200
    monkeypatch.setattr(auth_module, "OPEN_IDENTITY_ENVS", frozenset({"local"}))  # app_env=test
    for headers in (ALICE, {"authorization": "Bearer alice"}, {}):
        res = await client.get(f"{API}/threads", headers=headers)
        assert res.status_code == 401, headers


# --------------------------------------------------------------------------- chat stream


class _Scope:
    """Counts how many DB connections are checked out at any moment."""

    def __init__(self, conn):
        self.conn = conn
        self.open_now = 0

    def __call__(self):
        scope = self

        @contextlib.asynccontextmanager
        async def _ctx():
            scope.open_now += 1
            try:
                yield scope.conn
            finally:
                scope.open_now -= 1

        return _ctx()


class _PoolStub:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Scope(self.conn)()


class _Chunk:
    def __init__(self, content):
        self.content = content
        self.additional_kwargs = {}


class _FakeAgent:
    def __init__(self, scope: _Scope):
        self.scope = scope
        self.open_during_run: list[int] = []
        self.config: dict = {}

    async def astream_events(self, _input, version, config):
        self.open_during_run.append(self.scope.open_now)
        self.config = config
        for piece in ("Olá, ", "mundo"):
            yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk(piece)}}


async def test_streamed_chat_is_persisted_and_holds_no_db_connection(
    client, db_conn, fake_registry, monkeypatch
):
    from api.main import app

    scope = _Scope(db_conn)
    app.dependency_overrides[get_conn_scope] = lambda: scope
    monkeypatch.setattr(streaming, "get_pool", _async_value(_PoolStub(db_conn)))
    agent = _FakeAgent(scope)
    fake_registry({MODEL: {"name": "Echo", "agent": agent, "save_to_db": True, "capabilities": {}}})

    res = await client.post(
        f"{API}/chat/completions",
        headers=ALICE,
        json={
            "messages": [{"role": "user", "content": "oi"}],
            "model": MODEL,
            "stream": True,
            "session_id": "stream-1",
        },
    )
    await asyncio.gather(*streaming._DETACHED_TASKS)

    assert res.status_code == 200
    assert '"type":"text-delta"' in res.text and "Olá, " in res.text
    assert res.text.rstrip().endswith("data: [DONE]")
    # core-performance-01: the agent ran with ZERO connections checked out by the route
    assert agent.open_during_run == [0]
    # core-ai-09: every turn carries a step cap instead of LangGraph's 10007 default
    assert agent.config["recursion_limit"] == 25
    saved = await get_chat_messages(db_conn, "stream-1")
    assert [m["role"] for m in saved] == ["user", "assistant"]
    assert saved[1]["content"] == "Olá, mundo"


def _async_value(value):
    async def _get():
        return value

    return _get


# --------------------------------------------------------------------------- threads


async def test_threads_are_listed_read_and_deleted_only_by_their_owner(client, db_conn):
    from api.models.agents.history import ChatHistoryThread
    from api.repositories.agents.chat_history import save_chat

    await save_chat(
        db_conn,
        ChatHistoryThread(
            thread_id="alice-1",
            user_id="alice",
            agent_id=MODEL,
            messages=[{"role": "user", "content": "segredo"}],
            preview="segredo",
        ),
    )
    listed = (await client.get(f"{API}/threads", headers=ALICE)).json()["threads"]
    assert [t["thread_id"] for t in listed] == ["alice-1"]
    assert (await client.get(f"{API}/threads", headers=BOB)).json()["threads"] == []
    assert (await client.get(f"{API}/threads/alice-1", headers=BOB)).status_code == 403
    assert (await client.delete(f"{API}/threads/alice-1", headers=BOB)).status_code == 403
    mine = await client.get(f"{API}/threads/alice-1", headers=ALICE)
    assert mine.json()["messages"][0]["content"] == "segredo"
    assert (await client.delete(f"{API}/threads/alice-1", headers=ALICE)).status_code == 200
    assert (await client.get(f"{API}/threads/alice-1", headers=ALICE)).json()["messages"] == []


# --------------------------------------------------------------------------- uploads


async def test_upload_is_tracked_for_its_owner_and_deduplicated(client, db_conn, fake_registry):
    fake_registry({MODEL: {"name": "Echo", "capabilities": {}}})
    user = {"x-user-id": "upl-route-user"}
    user_dir = Path(api_config.UPLOADS_DIR) / "users" / "upl-route-user"
    try:
        files = {"file": ("nota.txt", b"conteudo da nota", "text/plain")}
        first = await client.post(
            "/api/v1/uploads", headers=user, files=files, params={"session_id": "th-1"}
        )
        assert first.status_code == 200, first.text
        url = first.json()["url"]
        row = await db_conn.fetchrow("SELECT * FROM user_uploads WHERE url = $1", url)
        assert row["owner_user_id"] == "upl-route-user" and row["visibility"] == "private"

        again = await client.post(
            "/api/v1/uploads", headers=user, files=files, params={"session_id": "th-1"}
        )
        assert again.json()["url"] == url  # same SHA256 in the same thread: no second copy
        assert await db_conn.fetchval("SELECT count(*) FROM user_uploads WHERE url=$1", url) == 1

        empty = await client.post(
            "/api/v1/uploads",
            headers=user,
            files={"file": ("vazio.txt", b"", "text/plain")},
        )
        assert empty.status_code == 400
    finally:
        shutil.rmtree(user_dir, ignore_errors=True)


# --------------------------------------------------------------------------- agent config


async def test_agent_config_is_versioned_and_isolated_per_tenant(client, fake_registry):
    fake_registry({MODEL: {"name": "Echo", "capabilities": {}}})
    url = f"{API}/{MODEL}/config"

    default = (await client.get(url, headers=ALICE)).json()
    assert default["active_version"] == 0

    v1 = await client.put(url, headers=ALICE, json={"system_prompt_markdown": "# Loja da Alice"})
    assert v1.status_code == 200, v1.text
    assert v1.json()["active_version"] == 1
    await client.put(url, headers=ALICE, json={"system_prompt_markdown": "# Alice v2"})

    versions = (await client.get(f"{url}/versions", headers=ALICE)).json()["versions"]
    assert [v["version"] for v in versions] == [2, 1]

    restored = await client.post(f"{url}/versions/1/activate", headers=ALICE)
    assert restored.json()["system_prompt_markdown"] == "# Loja da Alice"
    assert restored.json()["active_version"] == 3  # restore is a new version bump

    other = (await client.get(url, headers=BOB)).json()
    assert other["active_version"] == 0 and "Alice" not in other["system_prompt_markdown"]
    assert (await client.get(f"{API}/ghost-agent/config", headers=ALICE)).status_code == 404
    assert (await client.get(f"{url}/versions", headers=BOB)).json()["versions"] == []


@pytest.fixture(autouse=True)
def _reset_streaming_tasks():
    yield
    streaming._DETACHED_TASKS.clear()
