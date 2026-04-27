"""Sanity check: cache hit + usage_metadata + custo $ por turno.

Run from backend dir:
    uv run python scripts/test_cache_and_cost.py

Para cada modelo abaixo:
    turn#1 -> mensagem inicial do cliente
    sleep 10s
    turn#2 -> follow-up no mesmo thread_id (checkpointer rehidrata o prefixo)

Imprime usage_metadata e custo calculado pela tabela de preços em api.core.agents.models.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

dotenv.load_dotenv("/home/bellanda/code/promocar/.env", override=True)
dotenv.load_dotenv("/home/bellanda/code/promocar/config/env/.env.local", override=True)
dotenv.load_dotenv("/home/bellanda/code/promocar/config/env/.env.development", override=True)

from api.core.agents.custom_providers import init_model  # noqa: E402
from api.core.agents.models import ModelConfig, Models  # noqa: E402


def _load_vehicle_system_prompt() -> str:
    """Extract system_prompt from agents/vehicle_sales_agent/agent.py without importing the module
    (the module references a model id that may not exist in the current registry)."""
    path = Path("/home/bellanda/code/promocar/backend/agents/vehicle_sales_agent/agent.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "system_prompt":
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
    raise RuntimeError("system_prompt não encontrado em vehicle_sales_agent/agent.py")


SYSTEM_PROMPT = _load_vehicle_system_prompt()

USER_TURN_1 = "Oi, bom dia! Estou querendo saber mais sobre o Honda HR-V."
USER_TURN_2 = "E em relação a financiamento, qual taxa vocês trabalham hoje?"

WAIT_BETWEEN_TURNS_S = 10

CASES: list[tuple[str, ModelConfig]] = [
    ("OpenAI / GPT-5.4 nano", Models.OpenAI.GPT_5_4_NANO),
    ("Google / Gemini 3 Flash", Models.Google.GEMINI_3_FLASH_PREVIEW),
    ("Groq / GPT-OSS 120B", Models.Groq.GPT_OSS_120B),
    ("Chutes / Kimi K2.6 TEE", Models.Chutes.KIMI_K2_6_TEE),
    ("Chutes / Gemma 4 31B TEE", Models.Chutes.GEMMA_4_31B_TEE),
]


def _last_ai(state: dict) -> AIMessage | None:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage):
            return msg
    return None


def _cost_usd(usage: dict, cfg: ModelConfig) -> float:
    in_det = usage.get("input_token_details", {}) or {}
    cached = in_det.get("cache_read", 0) or 0
    fresh_input = max((usage.get("input_tokens", 0) or 0) - cached, 0)
    output = usage.get("output_tokens", 0) or 0
    return (
        fresh_input * cfg.input_price_per_1m / 1_000_000
        + cached * cfg.cached_input_price_per_1m / 1_000_000
        + output * cfg.output_price_per_1m / 1_000_000
    )


def _print_usage(label: str, msg: AIMessage | None, cfg: ModelConfig) -> None:
    if msg is None:
        print(f"  {label}: <no AIMessage>")
        return
    usage = getattr(msg, "usage_metadata", None) or {}
    if not usage:
        print(f"  {label}: usage_metadata vazio | response_metadata={msg.response_metadata}")
        return
    in_det = usage.get("input_token_details", {}) or {}
    out_det = usage.get("output_token_details", {}) or {}
    cost = _cost_usd(usage, cfg)
    print(
        f"  {label}: input={usage.get('input_tokens')} output={usage.get('output_tokens')} "
        f"total={usage.get('total_tokens')} cache_read={in_det.get('cache_read', 0)} "
        f"reasoning_out={out_det.get('reasoning', 0)} | cost=${cost:.6f}"
    )


async def _run_case(label: str, cfg: ModelConfig) -> None:
    print(f"\n=== {label} ({cfg.provider}/{cfg.model_id}) ===")
    try:
        model = init_model(cfg, streaming=False)
    except Exception as e:
        print(f"  init falhou: {type(e).__name__}: {e}")
        return

    saver = InMemorySaver()
    agent = create_agent(model=model, tools=[], system_prompt=SYSTEM_PROMPT, checkpointer=saver)
    config = {"configurable": {"thread_id": f"thr-{label}"}}

    try:
        out1 = await agent.ainvoke(
            {"messages": [{"role": "user", "content": USER_TURN_1}]}, config=config
        )
        _print_usage("turn#1", _last_ai(out1), cfg)
    except Exception as e:
        print(f"  turn#1 ERROR: {type(e).__name__}: {e}")
        return

    print(f"  ... aguardando {WAIT_BETWEEN_TURNS_S}s antes do turn#2 ...")
    await asyncio.sleep(WAIT_BETWEEN_TURNS_S)

    try:
        out2 = await agent.ainvoke(
            {"messages": [{"role": "user", "content": USER_TURN_2}]}, config=config
        )
        _print_usage("turn#2", _last_ai(out2), cfg)
        print(f"  state.messages no turn#2: {len(out2.get('messages', []))}")
    except Exception as e:
        print(f"  turn#2 ERROR: {type(e).__name__}: {e}")


async def main() -> None:
    print(f"system prompt chars: {len(SYSTEM_PROMPT)}")
    for label, cfg in CASES:
        await _run_case(label, cfg)


if __name__ == "__main__":
    asyncio.run(main())
