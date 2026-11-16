"""POST /agents/chat/completions with `stream=false` (the schema default).

Audit 2026-11 r2-kailos-be-portals-messaging-01: the one-shot path ran the agent without
`agent_id`/`tenant_id` metadata, so `usage_recorder` dropped the row (the monthly cap never saw the
spend) and no `chat_history` row claimed the thread (another user could resume the checkpoint).
Here the REAL `call_agent_async`/`execute_agent` run against a fake agent that drives the real
`usage_recorder` exactly like LangChain does.
"""

import uuid

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from api.core.agents.callbacks import usage_recorder
from api.repositories.agents.chat_history import get_chat_owner
from config import database as database_module
from config.settings import settings

CHAT = "/api/v1/agents/chat/completions"
MODEL = "echo-agent"
ALICE = {"x-user-id": "alice"}
BOB = {"x-user-id": "bob"}


class _PoolStub:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


class _FakeAgent:
    """ainvoke() reproduces what a chat model does with the config: callbacks see its metadata."""

    def __init__(self):
        self.configs: list[dict] = []

    async def ainvoke(self, _inputs, config):
        self.configs.append(config)
        run_id = uuid.uuid4()
        await usage_recorder.on_chat_model_start(
            {}, [[]], run_id=run_id, metadata=config.get("metadata")
        )
        ai = AIMessage(
            content="resposta",
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            response_metadata={
                "model_provider": "openrouter",
                "model_name": "anthropic/claude-haiku-5.5",
                "provider_cost_usd": 0.25,
            },
        )
        await usage_recorder.on_llm_end(
            LLMResult(generations=[[ChatGeneration(message=ai)]]), run_id=run_id
        )
        return {"messages": [ai]}


@pytest.fixture
def agent(fake_registry, db_conn, monkeypatch):
    fake = _FakeAgent()
    fake_registry({MODEL: {"agent": fake, "name": "Echo", "capabilities": {}}})
    # The recorder writes through its own pool connection; point it at the test transaction.
    monkeypatch.setattr(database_module, "asyncpg_pool", _PoolStub(db_conn))
    return fake


def _body(**extra):
    return {"messages": [{"role": "user", "content": "oi"}], "model": MODEL, **extra}


async def test_non_streaming_call_is_billed_to_the_tenant(client, db_conn, agent):
    res = await client.post(CHAT, headers=ALICE, json=_body(session_id="t-bill"))
    assert res.status_code == 200, res.text
    assert res.json()["choices"][0]["message"]["content"] == "resposta"
    row = await db_conn.fetchrow(
        "SELECT agent_id, user_id, tenant_id, cost_usd FROM agent_message_usage WHERE thread_id = $1",
        "t-bill",
    )
    assert row is not None, "usage_recorder dropped the row: metadata missing on the one-shot path"
    assert (row["agent_id"], row["user_id"], row["tenant_id"]) == (MODEL, "alice", "alice")
    assert float(row["cost_usd"]) == pytest.approx(0.25)


async def test_non_streaming_claims_the_thread_for_the_caller(client, db_conn, agent):
    res = await client.post(CHAT, headers=ALICE, json=_body(session_id="t-owned"))
    assert res.status_code == 200, res.text
    assert await get_chat_owner(db_conn, "t-owned") == ("alice", "t-owned")

    calls_before = len(agent.configs)
    other = await client.post(CHAT, headers=BOB, json=_body(session_id="t-owned"))
    assert other.status_code == 403, other.text
    assert len(agent.configs) == calls_before  # the victim's checkpoint was never resumed


async def test_non_streaming_over_cap_is_refused_before_the_model(
    client, db_conn, agent, monkeypatch
):
    monkeypatch.setattr(settings.agents, "monthly_budget_usd_per_tenant", 0.5)
    first = await client.post(CHAT, headers=ALICE, json=_body(session_id="t-cap-1"))
    assert first.status_code == 200, first.text  # 0.25 spent, still under 0.5
    second = await client.post(CHAT, headers=ALICE, json=_body(session_id="t-cap-2"))
    assert second.status_code == 200, second.text  # 0.50 spent now
    calls = len(agent.configs)
    third = await client.post(CHAT, headers=ALICE, json=_body(session_id="t-cap-3"))
    assert third.status_code == 429, third.text
    assert len(agent.configs) == calls
