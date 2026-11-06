"""Scenario replay runner: load validation, every expectation kind, bursts, isolation, summary.

DB-free and network-free: a scripted fake agent stands in for the real model.
"""

from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest

from api.core.agents.scenario_replay import (
    Scenario,
    ScenarioFile,
    ToolCallRecord,
    TurnOutput,
    langchain_turn_output,
    load_scenario_file,
    run_scenarios,
    summarize_results,
)

VALID_YAML = """
store_markdown: "# Loja"
fixtures: {menu: [1]}
scenarios:
  - id: synth-a
    category: pricing
    owner: L1
    turns: ["oi"]
    expect: {silent: false}
"""


def write_yaml(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "scenarios.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_valid_file_passes_fixtures_through(tmp_path):
    loaded = load_scenario_file(write_yaml(tmp_path, VALID_YAML))

    assert loaded.store_markdown == "# Loja" and loaded.fixtures == {"menu": [1]}
    assert loaded.scenarios[0].id == "synth-a"


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("id: synth-a", "id: foo-a"),
        ("category: pricing", "category: nope"),
        ("owner: L1", "owner: X"),
        ("expect: {silent: false}", "expect: {silentt: false}"),
    ],
)
def test_load_rejects_contract_violations(tmp_path, replacement, message):
    text = VALID_YAML.replace(replacement, message)
    with pytest.raises(ValueError):
        load_scenario_file(write_yaml(tmp_path, text))


def test_load_rejects_duplicate_ids(tmp_path):
    entry = "  - id: synth-a\n    category: pricing\n    owner: L1\n    turns: ['x']\n"
    with pytest.raises(ValueError, match="duplicate"):
        load_scenario_file(write_yaml(tmp_path, "scenarios:\n" + entry + entry))


def make_file(*scenarios: Scenario) -> ScenarioFile:
    return ScenarioFile(store_markdown="", fixtures={}, scenarios=list(scenarios))


def make_scenario(sid: str, expect: dict, turns=None) -> Scenario:
    return Scenario(sid, "pricing", "L1", "", {}, turns or ["oi"], expect)


class ScriptedAgent:
    def __init__(self, outputs: list[TurnOutput]):
        self.outputs = outputs
        self.received: list = []

    async def send(self, turn):
        self.received.append(turn)
        return self.outputs.pop(0)


async def run_with(expect: dict, output: TurnOutput, turns=None):
    scenario = make_scenario("synth-x", expect, turns)
    agent = ScriptedAgent([output])

    async def factory(_s, _f):
        return agent

    results = await run_scenarios(make_file(scenario), factory)
    return results[0], agent


def reply(text: str, *calls: ToolCallRecord) -> TurnOutput:
    return TurnOutput(replies=[text], tool_calls=list(calls))


HANDOFF = ToolCallRecord("handoff_to_human", {"reason": "Fornecedor cobrando boleto"})


@pytest.mark.parametrize(
    ("expect", "output", "passed"),
    [
        (
            {"handoff": True, "handoff_reason_must_match": ["fornecedor"]},
            reply("ok", HANDOFF),
            True,
        ),
        ({"handoff": True}, reply("ok"), False),
        ({"handoff": False}, reply("ok", HANDOFF), False),
        ({"handoff": True, "handoff_reason_must_match": ["desconto"]}, reply("", HANDOFF), False),
        (
            {"tools_called": ["a"], "tools_not_called": ["b"]},
            reply("x", ToolCallRecord("a", {})),
            True,
        ),
        ({"tools_called": ["a"]}, reply("x"), False),
        ({"tools_not_called": ["a"]}, reply("x", ToolCallRecord("a", {})), False),
        ({"silent": True}, TurnOutput(["", "SEM_RESPOSTA"]), True),
        ({"silent": True}, reply("olá"), False),
        ({"reply_must_not_match": ["desconto"]}, reply("Dou DESCONTO"), False),
        ({"reply_must_not_match": ["desconto"]}, reply("preço fixo"), True),
        ({"last_reply_must_match": ["pix", "10"]}, TurnOutput(["pix 10", "SEM_RESPOSTA"]), True),
        ({"last_reply_must_match": ["pix"]}, reply("cartão"), False),
        ({"max_matches": {"oi": 1}}, TurnOutput(["oi", "oi"]), False),
        ({"max_matches": {"oi": 2}}, TurnOutput(["oi", "oi"]), True),
    ],
)
async def test_each_expectation_kind(expect, output, passed):
    result, _ = await run_with(expect, output)

    assert result.passed is passed
    assert bool(result.failures) is not passed


async def test_failure_messages_are_human_readable():
    result, _ = await run_with(
        {"handoff": True, "reply_must_not_match": ["desconto"]}, reply("desconto")
    )

    assert any("expected handoff" in f for f in result.failures)
    assert any("reply 1 matched forbidden /desconto/" in f for f in result.failures)


async def test_burst_turn_is_sent_as_a_list():
    _, agent = await run_with({}, reply("ok"), turns=[["a", "b"]])

    assert agent.received == [["a", "b"]]


async def test_exception_is_isolated_and_only_filter_applies():
    async def factory(scenario, _f):
        if scenario.id == "synth-boom":
            raise RuntimeError("model down")
        return ScriptedAgent([reply("ok")])

    scenarios = make_file(
        make_scenario("synth-boom", {}),
        make_scenario("synth-ok", {}),
        make_scenario("synth-skip", {}),
    )
    results = await run_scenarios(
        scenarios, factory, only={"synth-boom", "synth-ok"}, max_concurrency=1
    )

    assert [r.id for r in results] == ["synth-boom", "synth-ok"]
    assert not results[0].passed and "RuntimeError: model down" in results[0].failures[0]
    assert results[1].passed


async def test_summarize_counts_by_category():
    async def factory(_s, _f):
        return ScriptedAgent([reply("ok")])

    file = make_file(
        make_scenario("synth-p", {"silent": False}), make_scenario("synth-f", {"silent": True})
    )
    summary = summarize_results(await run_scenarios(file, factory))

    assert summary["total"] == 2 and summary["failed_ids"] == ["synth-f"]
    assert summary["by_category"]["pricing"] == {"passed": 1, "failed": 1}


def test_langchain_turn_output_reads_only_new_ai_messages():
    old = SimpleNamespace(type="ai", text="antigo", tool_calls=[])
    human = SimpleNamespace(type="human", text="oi", tool_calls=[])
    tool_msg = SimpleNamespace(type="ai", text="", tool_calls=[{"name": "t", "args": {"q": 1}}])
    final = SimpleNamespace(type="ai", text=" feito ", tool_calls=[])

    out = langchain_turn_output([old], [old, human, tool_msg, final], "SEM_RESPOSTA")

    assert out.replies == ["feito"] and out.tool_calls == [ToolCallRecord("t", {"q": 1})]


async def test_anyio_runs_under_capacity_limit():
    active = peak = 0

    class Slow:
        async def send(self, _turn):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await anyio.sleep(0.01)
            active -= 1
            return reply("ok")

    async def factory(_s, _f):
        return Slow()

    await run_scenarios(
        make_file(*[make_scenario(f"synth-{i}", {}) for i in range(6)]), factory, max_concurrency=2
    )

    assert peak == 2
