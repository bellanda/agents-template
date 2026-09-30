"""Model registry + price table: the ONLY place that knows which models exist.

Two providers, and only these (central rule `ai-agents.md`, decision 2026-09-30): every chat
call (text, image, video) goes through **OpenRouter** with GLM 5.3 Flash, and **Groq** only
serves Whisper for audio transcription. One more provider here is one more inference route to
audit — `provider_order` below is what backs the "data stays in the US" answer given in privacy
policies and in Meta App Review (Data Handling).

The chat model and the model that reads media are the SAME (GLM 5.3 Flash is natively
multimodal). Swapping models = editing one `ModelConfig`; cost accounting, capabilities,
media enrichment and the frontend picker follow automatically.
"""

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

COST_DECIMAL_PLACES = 6
COST_SCALE = 10**COST_DECIMAL_PLACES


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    provider: str
    # Turns reasoning on upstream. `reasoning_effort` (low|medium|high) is more specific and
    # wins when both are set.
    reasoning: bool = False
    reasoning_effort: str | None = None
    # USD per 1M tokens. `cached_input_price_per_1m` applies when the provider reports
    # `cache_read`: a cached token usually costs a fraction of a fresh one, so treating them
    # as equal is wrong by an order of magnitude (in the expensive direction).
    input_price_per_1m: float = 0.0
    cached_input_price_per_1m: float = 0.0
    output_price_per_1m: float = 0.0
    # What the model accepts inline besides text. Declarative: they gate the chat upload
    # picker (frontend), the 400/415 guards (routes) and every branch of `media.py`, so
    # swapping the model here reconfigures media handling without touching code.
    # Text/documents are always supported (converted to text via MarkItDown/OCR — no flag).
    supports_image_input: bool = False
    supports_pdf_input: bool = False
    supports_audio_input: bool = False
    supports_video_input: bool = False
    # OpenRouter upstream routing: the same slug is served by dozens of upstreams with
    # different price, quantization and JURISDICTION. With `allow_provider_fallbacks=False`
    # OpenRouter tries each one IN ORDER and fails if all fail — it never leaves this list.
    provider_order: tuple[str, ...] = ()
    allow_provider_fallbacks: bool = True


def model_capabilities_dict(cfg: "ModelConfig") -> dict[str, bool]:
    """Serializable snapshot of the capability flags (GET /agents, model catalog)."""
    return {
        "image_input": cfg.supports_image_input,
        "pdf_input": cfg.supports_pdf_input,
        "audio_input": cfg.supports_audio_input,
        "video_input": cfg.supports_video_input,
        "reasoning": cfg.reasoning,
    }


def round_cost_up(value: float) -> float:
    """Round a USD amount UP to COST_DECIMAL_PLACES — a spend cap must never under-bill."""
    return math.ceil(value * COST_SCALE) / COST_SCALE


def compute_cost_usd(usage: dict[str, Any] | None, cfg: ModelConfig) -> float:
    """Convert a LangChain `usage_metadata` dict into USD using the registry's price table.

    Cached tokens are billed at cached_input_price_per_1m; the remainder of input tokens
    at input_price_per_1m. Output tokens (reasoning included) at output_price_per_1m.
    This is the FALLBACK: when OpenRouter reports `provider_cost_usd` (real upstream cost)
    the usage repository prefers it.
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
    return round_cost_up(raw)


# `ChatOpenRouter` subclasses `ChatOpenAI`, so LangChain may stamp OpenAI-family names in
# `response_metadata.model_provider` before our subclass rewrites it. All of them map to
# "openrouter": without this `find_model_config` misses and the call is billed as ZERO, silently.
PROVIDER_ALIASES: dict[str, str] = {
    "openai": "openrouter",
    "openai_chat": "openrouter",
    "openai_responses": "openrouter",
    "chat_openai": "openrouter",
    "chat_openrouter": "openrouter",
    "chat_groq": "groq",
}


def canonical_provider(provider: str) -> str:
    return PROVIDER_ALIASES.get(provider, provider)


class Models:
    """Model registry. Use `init_model(Models.OpenRouter.NAME)` to instantiate."""

    class OpenRouter:
        # Multi-provider gateway (OpenAI-compatible API) and the ONLY chat path of the stack.
        # `model_id` is the OpenRouter slug. The price below is the first upstream's; in
        # practice it is rarely used, because OpenRouter returns the REAL upstream cost in
        # `usage.cost` and `repositories/agents/usage.py` prefers that number.
        GLM_5_3_FLASH = ModelConfig(
            "z-ai/glm-5.3-flash",
            "openrouter",
            reasoning=True,
            reasoning_effort="high",
            input_price_per_1m=0.15,
            output_price_per_1m=0.50,
            supports_image_input=True,
            supports_video_input=True,
            # GLM 5.3 Flash does NOT take PDF or audio inline (OpenRouter catalog: text, image,
            # video). So audio is Whisper-or-nothing and PDFs go through MarkItDown / page OCR
            # (`ocr.py`, which renders pages to images). A model with `file`/`audio` input
            # re-enables both branches of `media.py` by flipping these flags.
            supports_pdf_input=False,
            supports_audio_input=False,
            # `allow_fallbacks=False` + this order is a JURISDICTION statement, not a price one.
            # This model talks to end customers and summarizes whole transcripts; every upstream
            # below is US-based, and that is what privacy policies and the Meta App Review Data
            # Handling answer declare. With fallbacks on, a 429 silently reroutes to ANY
            # upstream of the slug — Z.AI itself included, in China — and those declarations
            # become false with no signal. Four in line make a 429 reroute INSIDE the list
            # instead of becoming an error.
            #
            # The ENTRY filter for this list is `tool_choice: required`/`function`, not uptime
            # nor price: agents force a tool call, and `with_structured_output(
            # method=function_calling)` does too. Measured on 2026-09-17 via
            # `GET openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints`, these announce
            # `tools` but return `supports_tool_choice.required=false` — they would enter with
            # 99% uptime and answer 400 on EVERY call that has a tool: BaseTen, Relace, Novita,
            # Parasail, GMICloud, Z.AI. Query that endpoint before touching this tuple.
            #
            # CoreWeave was removed: it serves nvfp4 and was the endpoint that zeroed
            # (`uptime_last_30m = 0`) in the cascading 429 of 2026-09-17. DeepInfra stays LAST on
            # purpose: it is the cheapest ($0.075/$0.25) but serves fp4, and more aggressive
            # quantization hurts instruction-following and tool calling — it is the backstop,
            # not a preference. Fireworks, Together and Cloudflare charge the same
            # ($0.15/$0.50), so the order among them is free.
            provider_order=("fireworks", "together", "cloudflare", "deepinfra"),
            allow_provider_fallbacks=False,
        )

    class Groq:
        # NOT a chat model — audio transcription only, orders of magnitude cheaper than
        # sending audio to a multimodal model. It lives here so cost accounting finds its
        # provider/model_id; the call is a multipart POST in `media.py` (the transcription
        # endpoint is not OpenAI-chat-compatible and does not fit `init_model`). Billed per
        # HOUR of audio, not per token — token prices stay zero on purpose, see
        # WHISPER_USD_PER_HOUR in media.py.
        WHISPER_LARGE_V3_TURBO = ModelConfig(
            "whisper-large-v3-turbo",
            "groq",
            supports_audio_input=True,
        )


def iter_model_configs() -> Iterator[ModelConfig]:
    """Every `ModelConfig` declared in the `Models` namespaces."""
    for namespace in vars(Models).values():
        if not isinstance(namespace, type):
            continue
        for value in vars(namespace).values():
            if isinstance(value, ModelConfig):
                yield value


def find_model_config(provider: str, model_id: str) -> ModelConfig | None:
    """Lookup by (provider, model_id), normalizing LangChain's provider aliases."""
    canonical = canonical_provider(provider)
    for config in iter_model_configs():
        if config.provider == canonical and config.model_id == model_id:
            return config
    return None


def find_model_config_by_id(model_id: str) -> ModelConfig | None:
    """Lookup by model_id alone — what tenant configs and yaml persist (e.g. "z-ai/glm-5.3-flash")."""
    for config in iter_model_configs():
        if config.model_id == model_id:
            return config
    return None
