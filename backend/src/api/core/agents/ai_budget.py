"""Monthly AI spend cap per tenant: ONE canonical check for chats and LLM jobs.

Audit 2026-11-13 skills-backend-02. Cost is already recorded for every call
(`agent_message_usage`, via `usage_recorder`) but nothing READ it to stop spending: a tenant in
a tool loop, or a cron over a stale base, burned money until someone read the invoice.

Policy (the value) is the app's, measurement is the template's:
  * template default = `settings.agents.monthly_budget_usd_per_tenant` (0 disables the cap);
  * `check` reads `agent_message_usage` through `get_tenant_cost_usd_since`, which every app's
    usage repository must provide with its own tenant mapping (kailos/emporion: organization,
    optimuslar: the user, nexarena/akmeo/template: the `tenant_id` column);
  * an app whose cap is richer than one number (kailos/emporion per-store override in
    `organizations.settings`, akmeo `default_ai_monthly_budget_usd`) keeps that policy in its own
    `services/agents/ai_budget.py` and enforces it at its own call sites; it either overrides
    `check` here (kailos does) or leaves the template knob at 0, in which case `complete*`
    does NOT cap by itself and the explicit gates are the only protection.

Callers:
  * authenticated chat route: `await ensure_within_budget(conn, tenant_id)` BEFORE the agent runs;
  * LLM jobs: `llm.complete*` calls `enforce_for_usage(usage)` ONLY when the UsageContext carries
    a `tenant_id` (and only when a cap is configured). A job that omits `tenant_id` is not
    capped by this module: pass it, or call the app's own gate first.

The month is measured in UTC (`month_start_utc`); apps with a store timezone override the window.
Fail-OPEN only on infrastructure errors in `enforce_for_usage` (database unreachable, timeout): a
down cap query must not take the product down, it is logged loudly instead. A programming error
(ImportError, missing repository function, wrong SQL/column, TypeError) propagates: it must break
the call and the test, never silently disable the cap (audit 2026-11 r2-emporion-be-06). A tenant
that is over the cap fails CLOSED.
"""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg
from asyncpg.connection import Connection
from fastapi import HTTPException, status

from api.core.logging import get_logger
from config import database as database_module
from config.settings import settings

log = get_logger(__name__)

# What "the cap query could not run" means: the database/pool is unreachable or slow. Anything
# else raised while checking (ImportError, AttributeError, UndefinedColumnError...) is a bug.
_INFRA_ERRORS: tuple[type[BaseException], ...] = (
    OSError,
    TimeoutError,
    asyncpg.InterfaceError,
    asyncpg.PostgresConnectionError,
    asyncpg.InsufficientResourcesError,
    # Class 57: statement timeout / cancel, admin_shutdown + crash_shutdown (a Postgres restart
    # during a deploy), idle_session_timeout, cannot_connect_now (still starting up).
    asyncpg.OperatorInterventionError,
)

BUDGET_EXCEEDED_MESSAGE = (
    "O limite mensal de uso de IA desta conta foi atingido. "
    "Fale com o administrador para liberar mais uso."
)


class AiBudgetExceededError(Exception):
    """The tenant spent its monthly AI cap. Message is user-facing (pt-BR)."""

    def __init__(self, status_: BudgetStatus) -> None:
        super().__init__(BUDGET_EXCEEDED_MESSAGE)
        self.status = status_


@dataclass(frozen=True)
class BudgetStatus:
    spent_usd: float
    budget_usd: float | None  # None = no cap

    @property
    def exceeded(self) -> bool:
        return self.budget_usd is not None and self.spent_usd >= self.budget_usd


async def budget_for_tenant(conn: Connection, tenant_id: str) -> float | None:
    """Cap in USD for the tenant, or None for "no cap". Apps override this one function."""
    value = float(settings.agents.monthly_budget_usd_per_tenant or 0)
    return value if value > 0 else None


async def check(conn: Connection, tenant_id: str) -> BudgetStatus:
    """How much the tenant spent this month and what its cap is (None = no cap)."""
    budget = await budget_for_tenant(conn, tenant_id)
    if budget is None:
        return BudgetStatus(spent_usd=0.0, budget_usd=None)
    # Lazy import: each app's usage repository maps `tenant_id` to its own column.
    from api.repositories.agents.usage import get_tenant_cost_usd_since, month_start_utc

    spent = await get_tenant_cost_usd_since(conn, tenant_id, month_start_utc())
    return BudgetStatus(spent_usd=spent, budget_usd=budget)


async def ensure_within_budget(conn: Connection, tenant_id: str | None) -> None:
    """Raise `AiBudgetExceededError` when the tenant is over its cap. No tenant = no check."""
    if not tenant_id:
        return
    result = await check(conn, tenant_id)
    if result.exceeded:
        log.warning(
            "ai_budget_exceeded",
            tenant_id=tenant_id,
            spent_usd=result.spent_usd,
            budget_usd=result.budget_usd,
        )
        raise AiBudgetExceededError(result)


def budget_http_exception() -> HTTPException:
    """429 with the clear message, for routes (the chat returns it before calling the model)."""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=BUDGET_EXCEEDED_MESSAGE
    )


async def enforce_for_usage(tenant_id: str | None) -> None:
    """Cap check for code that has no connection at hand (LLM jobs, `llm.complete*`).

    Borrows a pool connection for the single query and returns it before the model call.
    """
    if not tenant_id:
        return
    try:
        pool = await database_module.get_pool()
        async with pool.acquire() as conn:
            result = await check(conn, tenant_id)
    except _INFRA_ERRORS:
        log.exception("ai_budget_check_failed_open", tenant_id=tenant_id)
        return
    if result.exceeded:
        log.warning(
            "ai_budget_exceeded",
            tenant_id=tenant_id,
            spent_usd=result.spent_usd,
            budget_usd=result.budget_usd,
        )
        raise AiBudgetExceededError(result)
