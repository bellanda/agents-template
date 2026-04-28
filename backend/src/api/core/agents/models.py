import math
from dataclasses import dataclass
from typing import Any

COST_DECIMAL_PLACES = 6
COST_SCALE = 10**COST_DECIMAL_PLACES


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    provider: str
    reasoning: bool = False  # emits reasoning_content in stream (Chutes/Cerebras)
    thinking: bool = False  # NVIDIA: chat_template_kwargs; Google: include_thoughts
    # OpenAI Responses API: none | low | medium | high | xhigh (see OpenAI reasoning docs)
    reasoning_effort: str | None = None
    # Pricing in USD per 1M tokens. cached_input_price applies when provider reports cache_read.
    input_price_per_1m: float = 0.0
    cached_input_price_per_1m: float = 0.0
    output_price_per_1m: float = 0.0


def compute_cost_usd(usage: dict[str, Any] | None, cfg: ModelConfig) -> float:
    """Convert a LangChain usage_metadata dict into USD using the registry's price table.

    Cached tokens are billed at cached_input_price_per_1m; the remainder of input tokens
    at input_price_per_1m. Output tokens (reasoning included) at output_price_per_1m.
    Always rounds UP to COST_DECIMAL_PLACES (never under-bills).
    """
    if not usage:
        return 0.0
    in_det = usage.get("input_token_details") or {}
    cached = int(in_det.get("cache_read") or 0)
    fresh_input = max(int(usage.get("input_tokens") or 0) - cached, 0)
    output = int(usage.get("output_tokens") or 0)
    raw = (
        fresh_input * cfg.input_price_per_1m
        + cached * cfg.cached_input_price_per_1m
        + output * cfg.output_price_per_1m
    ) / 1_000_000
    return math.ceil(raw * COST_SCALE) / COST_SCALE


# LangChain `response_metadata.model_provider` uses different names than our registry.
# Map the response value back to the registry's canonical provider key.
PROVIDER_ALIASES: dict[str, str] = {
    "google_genai": "google",
    "google_vertexai": "google",
    "openai_chat": "openai",
    "openai_responses": "openai",
    "chat_openai": "openai",
    "chat_groq": "groq",
    "chat_cerebras": "cerebras",
    "chat_nvidia": "nvidia",
}


def canonical_provider(provider: str) -> str:
    return PROVIDER_ALIASES.get(provider, provider)


def find_model_config(provider: str, model_id: str) -> ModelConfig | None:
    """Lookup a registered ModelConfig by (provider, model_id). Returns None if not found.

    Provider aliases (e.g. `google_genai` -> `google`) are normalized so LangChain's
    response_metadata names match what's declared in the Models registry.
    """
    canonical = canonical_provider(provider)
    for namespace in vars(Models).values():
        if not isinstance(namespace, type):
            continue
        for value in vars(namespace).values():
            if (
                isinstance(value, ModelConfig)
                and value.provider == canonical
                and value.model_id == model_id
            ):
                return value
    return None


class Models:
    """Model registry. Use init_model(Models.Provider.NAME) in each agent to instantiate."""

    class Chutes:
        KIMI_K2_6_TEE = ModelConfig(
            "moonshotai/Kimi-K2.6-TEE",
            "chutes",
            reasoning=True,
            input_price_per_1m=0.95,
            cached_input_price_per_1m=0.95,
            output_price_per_1m=4.00,
        )
        QWEN_3_6_27B_TEE = ModelConfig(
            "Qwen/Qwen3.6-27B-TEE",
            "chutes",
            reasoning=True,
            input_price_per_1m=0.50,
            cached_input_price_per_1m=0.50,
            output_price_per_1m=2.00,
        )
        GEMMA_4_31B_TEE = ModelConfig(
            "google/gemma-4-31B-turbo-TEE",
            "chutes",
            reasoning=True,
            input_price_per_1m=0.13,
            cached_input_price_per_1m=0.13,
            output_price_per_1m=0.38,
        )

    class Google:
        GEMINI_3_FLASH_PREVIEW = ModelConfig(
            "gemini-3-flash-preview",
            "google",
            thinking=True,
            input_price_per_1m=0.50,
            cached_input_price_per_1m=0.05,
            output_price_per_1m=3.00,
        )

    class OpenAI:
        GPT_5_4_NANO = ModelConfig(
            "gpt-5.4-nano",
            "openai",
            reasoning=True,
            reasoning_effort="high",
            input_price_per_1m=0.20,
            cached_input_price_per_1m=0.02,
            output_price_per_1m=1.25,
        )

    class Groq:
        GPT_OSS_120B = ModelConfig(
            "openai/gpt-oss-120b",
            "groq",
            input_price_per_1m=0.15,
            cached_input_price_per_1m=0.075,
            output_price_per_1m=0.60,
        )
        GPT_OSS_20B = ModelConfig(
            "openai/gpt-oss-20b",
            "groq",
            input_price_per_1m=0.075,
            cached_input_price_per_1m=0.0375,
            output_price_per_1m=0.30,
        )
        LLAMA_4_SCOUT = ModelConfig("meta-llama/llama-4-scout-17b-16e-instruct", "groq")

    class NVIDIA:
        NEMOTRON_3_SUPER_120B_A12B = ModelConfig(
            "nvidia/nemotron-3-super-120b-a12b",
            "nvidia",
            thinking=True,
            input_price_per_1m=0,
            cached_input_price_per_1m=0,
            output_price_per_1m=0,
        )
        NEMOTRON_3_NANO_30B_A3B = ModelConfig(
            "nvidia/nemotron-3-nano-30b-a3b",
            "nvidia",
            thinking=True,
            input_price_per_1m=0,
            cached_input_price_per_1m=0,
            output_price_per_1m=0,
        )
