"""One-shot LLM calls — the helper for everything that is NOT a chat agent.

Pick the smallest tool that does the job (the full spectrum, documented in
AGENTS_SUBSYSTEM.md §3):

    complete()             one prompt → one text answer. Summaries, rewrites, classification
                           into free text, "describe this", scheduled/batch jobs. No graph, no
                           checkpointer, no tools.
    complete_structured()  one prompt → one validated Pydantic object. Extraction, routing
                           decisions, scoring — whenever code (not a human) reads the answer.
    agents/<name>/         a `create_agent(...)` with tools, streaming, memory (checkpointer)
                           and a chat UI — see `agents/weather_agent` (tools) and
                           `agents/research_supervisor_agent` (subagent delegation).

Three things live here because they cannot live at every call site (pattern from akmeo's
agent worker, generalized 2026-09-30):

* **Process-wide CapacityLimiter** (`settings.agents.max_concurrent_llm`). A burst of runs
  without a cap fires hundreds of simultaneous requests and the provider 429s all of them.
* **Retry only what is transient** (429/5xx/timeouts, jittered exponential backoff). A bad
  credential or payload returns the same error N times slower, and hides the cause in the log.
* **Spend cap.** When the `UsageContext` carries a `tenant_id`, `complete*` first calls
  `ai_budget.enforce_for_usage` and raises `AiBudgetExceededError` if the tenant already spent its
  monthly cap (audit 2026-11-13 skills-backend-02). The limiter/retry live in `llm_limits.py` and
  are ALSO applied inside the chat model (`ChatOpenRouter`), so agents get them too.
* **Cost on every call.** `LlmResult.cost_usd` is the REAL upstream cost when OpenRouter reports
  it (`provider_cost_usd`), else the price-table estimate. Pass a `UsageContext` and the
  `usage_recorder` callback also persists the row in `agent_message_usage` — without one the
  call is invisible to any spend cap, so product flows must always pass it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from api.core.agents.ai_budget import enforce_for_usage
from api.core.agents.callbacks import usage_recorder
from api.core.agents.custom_providers import init_model
from api.core.agents.llm_limits import (  # noqa: F401  (re-exported: public API of this module)
    BACKOFF_BASE_SECONDS,
    BACKOFF_MAX_SECONDS,
    RETRYABLE_MARKERS,
    RETRYABLE_STATUS,
    is_retryable,
    with_llm_retry,
)
from api.core.agents.models import ModelConfig, Models, compute_cost_usd
from api.core.logging import get_logger

log = get_logger(__name__)

DEFAULT_MODEL: ModelConfig = Models.OpenRouter.CLAUDE_HAIKU_5_5


@dataclass(frozen=True, slots=True)
class UsageContext:
    """Who pays for a call — becomes `RunnableConfig.metadata` for the `usage_recorder`.

    `thread_id` + `agent_id` are required by the callback (without both it drops the row
    silently). Use a synthetic thread for non-chat work (e.g. `f"job:{job_id}"`) and a stable
    `agent_id` per purpose (e.g. "media-enrichment", "lead-scoring") — that is what lets you
    answer "how much did X cost this month".
    """

    thread_id: str
    agent_id: str
    user_id: str | None = None
    client_id: str | None = None
    tenant_id: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "client_id": self.client_id,
            "tenant_id": self.tenant_id,
        }

    def runnable_config(self) -> dict[str, Any]:
        """`config=` for `ainvoke`: the recorder must be passed explicitly on bare models."""
        return {"callbacks": [usage_recorder], "metadata": self.to_metadata()}


@dataclass(frozen=True, slots=True)
class LlmResult:
    message: AIMessage
    model_id: str
    cost_usd: float
    cost_is_real: bool
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Visible text only (reasoning lives in additional_kwargs, not here)."""
        return (self.message.text or "").strip()


@dataclass(frozen=True, slots=True)
class StructuredResult[T: BaseModel]:
    value: T
    raw: LlmResult


def cost_of(message: AIMessage, config: ModelConfig) -> tuple[float, bool]:
    """`(cost_usd, is_real)` — real when the gateway reported what the upstream charged."""
    reported = (message.response_metadata or {}).get("provider_cost_usd")
    if reported is not None:
        return float(reported), True
    return compute_cost_usd(message.usage_metadata or {}, config), False


def _as_messages(prompt: str | Sequence[BaseMessage], system: str | None) -> list[BaseMessage]:
    messages = [HumanMessage(content=prompt)] if isinstance(prompt, str) else list(prompt)
    return [SystemMessage(content=system), *messages] if system else messages


def _to_result(message: AIMessage, config: ModelConfig) -> LlmResult:
    cost, is_real = cost_of(message, config)
    return LlmResult(
        message=message,
        model_id=config.model_id,
        cost_usd=cost,
        cost_is_real=is_real,
        usage=dict(message.usage_metadata or {}),
    )


async def complete(
    prompt: str | Sequence[BaseMessage],
    *,
    usage: UsageContext | None,
    system: str | None = None,
    model: ModelConfig = DEFAULT_MODEL,
    tools: Sequence[BaseTool] | None = None,
    **overrides: Any,
) -> LlmResult:
    """One call, one answer. `overrides` go to `init_model` (max_tokens, temperature, ...).

    `tools` only BINDS them: the returned message may carry `tool_calls` that YOU execute.
    If you need the model to loop over tools until done, you want an agent, not this.

    Example:
        result = await complete(
            f"Resuma em 3 linhas:\\n\\n{text}",
            usage=UsageContext(thread_id=f"doc:{doc_id}", agent_id="doc-summary"),
            max_tokens=300,
        )
        summary = result.text
    """
    await enforce_for_usage(usage.tenant_id if usage else None)
    chat_model = init_model(model, streaming=False, **overrides)
    runnable = chat_model.bind_tools(list(tools)) if tools else chat_model
    config = usage.runnable_config() if usage else {}
    messages = _as_messages(prompt, system)

    async def call() -> AIMessage:
        return await runnable.ainvoke(messages, config=config)

    return _to_result(await with_llm_retry(call, label=model.model_id), model)


async def complete_structured[T: BaseModel](
    prompt: str | Sequence[BaseMessage],
    schema: type[T],
    *,
    usage: UsageContext | None,
    system: str | None = None,
    model: ModelConfig = DEFAULT_MODEL,
    **overrides: Any,
) -> StructuredResult[T]:
    """One call, one validated `schema` instance. Raises on a parsing failure.

    `method="function_calling"` (not json_schema): tool calling is the one capability every
    upstream in `provider_order` is REQUIRED to serve (see models.py), while strict
    `response_format` support varies per upstream. Reasoning is off by default — extraction
    needs no thinking and it only adds latency and output tokens; pass
    `reasoning_effort="high"` for judgment-heavy decisions.

    Example:
        class Lead(BaseModel):
            name: str | None
            intent: Literal["buy", "sell", "other"]

        lead = (await complete_structured(message_text, Lead, usage=ctx)).value
    """
    await enforce_for_usage(usage.tenant_id if usage else None)
    overrides.setdefault("reasoning", False)
    overrides.setdefault("reasoning_effort", None)
    chat_model = init_model(model, streaming=False, **overrides)
    runnable = chat_model.with_structured_output(
        schema, method="function_calling", include_raw=True
    )
    config = usage.runnable_config() if usage else {}
    messages = _as_messages(prompt, system)

    async def call() -> dict[str, Any]:
        return await runnable.ainvoke(messages, config=config)

    output = await with_llm_retry(call, label=f"{model.model_id}:{schema.__name__}")
    parsed = output.get("parsed")
    if output.get("parsing_error") is not None or not isinstance(parsed, schema):
        raise ValueError(
            f"Structured output did not validate as {schema.__name__}: "
            f"{output.get('parsing_error')!r}"
        )
    return StructuredResult(value=parsed, raw=_to_result(output["raw"], model))
