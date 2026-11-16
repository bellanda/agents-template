"""One canonical per-tenant monthly AI cap (audit 2026-11-13 skills-backend-02).

The chat answers 429 BEFORE any model work when the tenant is over its cap, and
`llm.complete*` refuses to call the model for a tenant over its cap (jobs are covered by the
same check without remembering to call it).
"""

import asyncpg
import pytest

from api.core.agents import ai_budget, llm
from api.core.agents.ai_budget import AiBudgetExceededError
from api.models.agents.usage import AgentMessageUsage
from api.repositories.agents.usage import insert_agent_message_usage
from api.routes.agents import chat as chat_module
from config import database as database_module
from config.settings import settings

CHAT = "/api/v1/agents/chat/completions"
MODEL = "echo-agent"
ALICE = {"x-user-id": "alice"}


async def _spend(conn, tenant: str, usd: float) -> None:
    await insert_agent_message_usage(
        conn,
        AgentMessageUsage(
            thread_id="t",
            message_id=f"m-{tenant}-{usd}",
            tenant_id=tenant,
            agent_id="a",
            provider="openrouter",
            model_id="anthropic/claude-haiku-5.5",
            cost_usd=usd,
        ),
    )


@pytest.fixture
def cap(monkeypatch):
    """Set the template cap on the live AgentsSettings instance."""

    def set_cap(usd: float) -> None:
        monkeypatch.setattr(settings.agents, "monthly_budget_usd_per_tenant", usd)

    return set_cap


class _PoolStub:
    """`get_pool()` stand-in handing out the test transaction connection."""

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


async def test_check_reports_spend_and_cap(db_conn, cap):
    cap(5.0)
    await _spend(db_conn, "alice", 2.0)
    status = await ai_budget.check(db_conn, "alice")
    assert (status.spent_usd, status.budget_usd, status.exceeded) == (2.0, 5.0, False)
    await _spend(db_conn, "alice", 3.0)
    assert (await ai_budget.check(db_conn, "alice")).exceeded
    # another tenant is unaffected
    assert not (await ai_budget.check(db_conn, "bob")).exceeded


async def test_zero_cap_disables_the_check(db_conn, cap):
    cap(0)
    await _spend(db_conn, "alice", 999.0)
    assert (await ai_budget.check(db_conn, "alice")).budget_usd is None
    await ai_budget.ensure_within_budget(db_conn, "alice")  # does not raise


async def test_chat_is_refused_before_the_agent_runs_when_over_cap(
    client, db_conn, cap, fake_registry, monkeypatch
):
    cap(1.0)
    await _spend(db_conn, "alice", 1.5)
    fake_registry({MODEL: {"name": "Echo", "capabilities": {}}})
    calls = []

    async def _call(**kw):
        calls.append(kw)
        return "ok"

    monkeypatch.setattr(chat_module, "call_agent_async", _call)
    body = {"messages": [{"role": "user", "content": "oi"}], "model": MODEL}

    res = await client.post(CHAT, headers=ALICE, json=body)
    assert res.status_code == 429, res.text
    assert "limite mensal" in res.json()["detail"]
    assert calls == []

    # a tenant under its cap still gets served
    ok = await client.post(CHAT, headers={"x-user-id": "bob"}, json=body)
    assert ok.status_code == 200, ok.text


async def test_llm_complete_refuses_without_calling_the_model_when_over_cap(
    db_conn, cap, monkeypatch
):
    cap(1.0)
    await _spend(db_conn, "alice", 2.0)
    monkeypatch.setattr(database_module, "get_pool", _async_value(_PoolStub(db_conn)))

    def _must_not_build(*_a, **_k):
        raise AssertionError("model was built for a tenant over its cap")

    monkeypatch.setattr(llm, "init_model", _must_not_build)
    usage = llm.UsageContext(thread_id="job:1", agent_id="job", tenant_id="alice")
    with pytest.raises(AiBudgetExceededError):
        await llm.complete("resuma", usage=usage)


def _async_value(value):
    async def _get():
        return value

    return _get


async def test_infra_error_in_the_cap_query_fails_open_but_a_bug_does_not(cap, monkeypatch):
    """Database down = the product keeps working (logged); a programming error must surface,
    otherwise a missing repository function silently turns the cap off (audit 2026-11
    r2-emporion-be-06)."""
    cap(1.0)

    async def _db_down():
        raise OSError("pool unreachable")

    monkeypatch.setattr(database_module, "get_pool", _db_down)
    await ai_budget.enforce_for_usage("alice")  # fail-open, does not raise

    # A Postgres restart (deploy) surfaces as admin_shutdown, a class-57 error that is infrastructure too.
    async def _restarting():
        raise asyncpg.AdminShutdownError("terminating connection due to administrator command")

    monkeypatch.setattr(database_module, "get_pool", _restarting)
    await ai_budget.enforce_for_usage("alice")  # fail-open, does not raise

    async def _bug():
        raise ImportError("cannot import name get_tenant_cost_usd_since")

    monkeypatch.setattr(database_module, "get_pool", _bug)
    with pytest.raises(ImportError):
        await ai_budget.enforce_for_usage("alice")
