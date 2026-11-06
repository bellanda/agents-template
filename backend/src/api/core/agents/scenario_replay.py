"""Anomaly-catalog replay runner: scenarios.yaml → real agent (fake tools) → pass/fail report.

Fleet contract (central ref `anomaly-catalog.md`): every app keeps a catalog of cases that went
wrong (or could) and replays them against the REAL model with fake tools, OUTSIDE check.sh and
pytest (costs money). Every prod incident becomes a `prod-*` scenario BEFORE the fix.

This module is domain-free: it loads/validates the YAML, runs scenarios concurrently (anyio) and
checks `expect`. The APP supplies an `AgentFactory` that builds its real prompt + fake tools and
returns an `AgentUnderTest`; the runner knows nothing about langchain/tools/prompts.
The factory MUST pass a `UsageContext` labelled as eval (never LLM without UsageContext, so the
cost of the run is attributed and capped).

YAML shape: `store_markdown` (optional L2 fixture), `fixtures` (app-specific, untouched),
`scenarios[]` with id (`prod-`|`synth-`), category, owner (L1|L2|L3|G), note, context, turns
(a list item = burst sent together) and `expect` (handoff, handoff_reason_must_match,
tools_called, tools_not_called, silent, reply_must_not_match, last_reply_must_match, max_matches).
Expectation checks live in `scenario_checks.py` (ship both). Optional helper `langchain_turn_output` converts a LangGraph state diff into a `TurnOutput`.
"""

from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import anyio
import yaml

from api.core.agents.scenario_checks import check_handoff, check_replies, check_tools
from api.core.logging import get_logger

log = get_logger(__name__)

ID_PREFIXES = ("prod-", "synth-")
CATEGORIES = frozenset(
    {
        "catalog", "pricing", "delivery", "order_followup", "hours",
        "dine_in", "non_customer", "manipulation", "media", "conversation",
    }
)  # fmt: skip
OWNERS = frozenset({"L1", "L2", "L3", "G"})
EXPECT_KEYS = frozenset(
    {
        "handoff", "handoff_reason_must_match", "tools_called", "tools_not_called",
        "silent", "reply_must_not_match", "last_reply_must_match", "max_matches",
    }
)  # fmt: skip

Turn = str | list[str]


@dataclass(frozen=True)
class Scenario:
    id: str
    category: str
    owner: str
    note: str
    context: dict[str, Any]
    turns: list[Turn]
    expect: dict[str, Any]


@dataclass(frozen=True)
class ScenarioFile:
    store_markdown: str
    fixtures: dict[str, Any]
    scenarios: list[Scenario]


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class TurnOutput:
    replies: list[str]
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


class AgentUnderTest(Protocol):
    async def send(self, turn: Turn) -> TurnOutput: ...


AgentFactory = Callable[[Scenario, ScenarioFile], Awaitable[AgentUnderTest]]


@dataclass(frozen=True)
class ScenarioResult:
    id: str
    category: str
    owner: str
    passed: bool
    failures: list[str]
    replies: list[str]
    tool_calls: list[ToolCallRecord]


# --------------------------------------------------------------------------- loading


def parse_scenario(raw: Any, index: int) -> Scenario:
    where = f"scenarios[{index}]"
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: expected a mapping, received {type(raw).__name__}")
    scenario_id = str(raw.get("id", ""))
    where = f"{where} ({scenario_id!r})"
    if not scenario_id.startswith(ID_PREFIXES):
        raise ValueError(f"{where}: id must start with one of {ID_PREFIXES}")
    if raw.get("category") not in CATEGORIES:
        raise ValueError(f"{where}: category {raw.get('category')!r} not in {sorted(CATEGORIES)}")
    if raw.get("owner") not in OWNERS:
        raise ValueError(f"{where}: owner {raw.get('owner')!r} not in {sorted(OWNERS)}")
    turns = raw.get("turns")
    if not isinstance(turns, list) or not turns:
        raise ValueError(f"{where}: turns must be a non-empty list, received {turns!r}")
    expect = raw.get("expect") or {}
    unknown = set(expect) - EXPECT_KEYS
    if unknown:
        raise ValueError(
            f"{where}: unknown expect keys {sorted(unknown)}; allowed {sorted(EXPECT_KEYS)}"
        )
    return Scenario(
        id=scenario_id,
        category=raw["category"],
        owner=raw["owner"],
        note=str(raw.get("note", "")),
        context=raw.get("context") or {},
        turns=turns,
        expect=expect,
    )


def load_scenario_file(path: Path) -> ScenarioFile:
    """Parse + validate a scenarios YAML; any contract violation raises ValueError with context."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw_scenarios = data.get("scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise ValueError(f"{path}: 'scenarios' must be a non-empty list")
    scenarios = [parse_scenario(raw, index) for index, raw in enumerate(raw_scenarios)]
    duplicated = [sid for sid, n in Counter(s.id for s in scenarios).items() if n > 1]
    if duplicated:
        raise ValueError(f"{path}: duplicate scenario ids {duplicated}")
    return ScenarioFile(
        store_markdown=data.get("store_markdown") or "",
        fixtures=data.get("fixtures") or {},
        scenarios=scenarios,
    )


# --------------------------------------------------------------------------- running


async def run_one_scenario(
    scenario: Scenario,
    scenario_file: ScenarioFile,
    agent_factory: AgentFactory,
    silence_token: str,
    handoff_tool: str,
    handoff_reason_keys: tuple[str, ...],
) -> ScenarioResult:
    replies: list[str] = []
    calls: list[ToolCallRecord] = []
    try:
        agent = await agent_factory(scenario, scenario_file)
        for turn in scenario.turns:
            output = await agent.send(turn)
            replies.extend(output.replies)
            calls.extend(output.tool_calls)
        failures = [
            *check_handoff(scenario.expect, calls, handoff_tool, handoff_reason_keys),
            *check_tools(scenario.expect, calls),
            *check_replies(scenario.expect, replies, silence_token),
        ]
    except Exception as error:
        failures = [f"exception: {type(error).__name__}: {error}"]
    return ScenarioResult(
        scenario.id, scenario.category, scenario.owner, not failures, failures, replies, calls
    )


async def run_scenarios(
    scenario_file: ScenarioFile,
    agent_factory: AgentFactory,
    *,
    only: set[str] | None = None,
    max_concurrency: int = 4,
    silence_token: str = "SEM_RESPOSTA",
    handoff_tool: str = "handoff_to_human",
    handoff_reason_keys: tuple[str, ...] = ("reason", "summary"),
) -> list[ScenarioResult]:
    """Run the (optionally filtered) scenarios with bounded concurrency; results keep file order."""
    selected = [s for s in scenario_file.scenarios if only is None or s.id in only]
    results: dict[str, ScenarioResult] = {}
    limiter = anyio.CapacityLimiter(max_concurrency)

    async def worker(scenario: Scenario) -> None:
        async with limiter:
            results[scenario.id] = await run_one_scenario(
                scenario,
                scenario_file,
                agent_factory,
                silence_token,
                handoff_tool,
                handoff_reason_keys,
            )

    async with anyio.create_task_group() as task_group:
        for scenario in selected:
            task_group.start_soon(worker, scenario)
    return [results[s.id] for s in selected]


def summarize_results(results: Sequence[ScenarioResult]) -> dict[str, Any]:
    """Totals + per-category pass/fail + failed ids."""
    by_category: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = by_category.setdefault(result.category, {"passed": 0, "failed": 0})
        bucket["passed" if result.passed else "failed"] += 1
    passed = sum(1 for r in results if r.passed)
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "by_category": by_category,
        "failed_ids": [r.id for r in results if not r.passed],
    }


def log_results(results: Sequence[ScenarioResult]) -> None:
    for result in results:
        if result.passed:
            log.info("scenario_passed", scenario_id=result.id, category=result.category)
        else:
            log.warning(
                "scenario_failed",
                scenario_id=result.id,
                category=result.category,
                owner=result.owner,
                failures=result.failures,
            )
    log.info("scenario_replay_summary", **summarize_results(results))


# --------------------------------------------------------------------------- langchain helper


def langchain_turn_output(
    messages_before: Sequence[Any],
    messages_after: Sequence[Any],
    silence_token: str = "SEM_RESPOSTA",
) -> TurnOutput:
    """AI texts + tool calls added to a LangGraph `messages` state during one turn.

    Duck-typed (no langchain import): AI messages have `type == "ai"`, `.text` and `.tool_calls`.
    Empty texts are kept as "" when they carry no tool calls only; silence tokens stay as-is so
    the checks can treat them as silent.
    """
    replies: list[str] = []
    calls: list[ToolCallRecord] = []
    for message in list(messages_after)[len(messages_before) :]:
        if getattr(message, "type", None) != "ai":
            continue
        calls.extend(
            ToolCallRecord(c["name"], dict(c.get("args") or {})) for c in message.tool_calls or []
        )
        text = (message.text if isinstance(message.text, str) else str(message.text)).strip()
        if text or not message.tool_calls:
            replies.append(text)
    return TurnOutput(replies=replies, tool_calls=calls)
