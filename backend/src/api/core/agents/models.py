"""Model registry + price table: the ONLY place that knows which models exist.

One provider, and only this one (central rule `ai-agents.md`): every call goes through
**OpenRouter** — chat (text, image) with Claude Haiku 5.5 (reasoning effort low) and audio
transcription with Whisper on its STT endpoint (Groq-direct dropped 2026-10-22, user decision).
One more provider here is one more inference route to audit — `provider_order` below is what backs the "data stays in the US" answer given in privacy
policies and in Meta App Review (Data Handling).

Stack history: GLM 5.3 Flash until 2026-10-10, then Haiku 5.5 ("Haiku as the universal
default", user decision). Bake-off on Kailos' real Promocar config (144 simulated WhatsApp
conversations, blind-judged): Haiku low costs about half of GLM high (US$ 3.5 vs 6.3 per 1000
conversations, thanks to prompt caching), has the same latency (p50 ~5s, p90 ~8.7s) and
invents ~6-9x fewer facts. Higher efforts are too slow for WhatsApp (medium p90 12s, xhigh p90
28s, max p50 79s).

The chat model and the model that reads media are the SAME for text + image. Video has no
native path on Haiku: `media.py` turns it into sampled frames (image input). Swapping models =
editing one `ModelConfig`; cost accounting, capabilities, media enrichment and the frontend
picker follow automatically.
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
    # Turns reasoning on upstream. `reasoning_effort` (low|medium|high|xhigh|max) is more
    # specific and wins when both are set.
    reasoning: bool = False
    reasoning_effort: str | None = None
    # USD per 1M tokens. `cached_input_price_per_1m` applies when the provider reports
    # `cache_read`: a cached token usually costs a fraction of a fresh one, so treating them
    # as equal is wrong by an order of magnitude (in the expensive direction).
    input_price_per_1m: float = 0.0
    cached_input_price_per_1m: float = 0.0
    output_price_per_1m: float = 0.0
    # Anthropic bills prompt-cache WRITES at a premium over fresh input (1.25x for Haiku 5.5);
    # `usage_metadata.input_token_details.cache_creation` reports them. 0.0 = the provider has
    # no write premium (implicit-cache models), so creation tokens stay billed as fresh input.
    cache_write_price_per_1m: float = 0.0
    # Sends top-level `"cache_control": {"type": "ephemeral"}` in the OpenRouter request body.
    # WHY: Anthropic models cache NOTHING implicitly — without that field there is no cache at
    # all (measured 2026-10-10 on Haiku 5.5). With it, the first call reports `cache_creation`
    # and the following ones `cache_read` (~90% off input). Implicit-cache models leave it off.
    prompt_cache_control: bool = False
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
    # False = not a chat model (Whisper): `init_model` refuses it. Until 2026-10-22 the guard was
    # the provider ("groq" was never instantiable); with Whisper on OpenRouter the provider no
    # longer tells them apart, and `init_model_by_id` would build a chat model on a STT slug.
    is_chat_model: bool = True


def model_capabilities_dict(cfg: "ModelConfig") -> dict[str, bool]:
    """Serializable snapshot of the capability flags (GET /agents, model catalog)."""
    return {
        "image_input": cfg.supports_image_input,
        "pdf_input": cfg.supports_pdf_input,
        "audio_input": cfg.supports_audio_input,
        # True also for the frames fallback in `media.py` (video → sampled images): any model
        # that takes images can "accept" a video, so the chat upload picker must keep offering it.
        "video_input": cfg.supports_video_input or cfg.supports_image_input,
        "reasoning": cfg.reasoning,
    }


def round_cost_up(value: float) -> float:
    """Round a USD amount UP to COST_DECIMAL_PLACES — a spend cap must never under-bill."""
    return math.ceil(value * COST_SCALE) / COST_SCALE


def compute_cost_usd(usage: dict[str, Any] | None, cfg: ModelConfig) -> float:
    """Convert a LangChain `usage_metadata` dict into USD using the registry's price table.

    Cache reads are billed at cached_input_price_per_1m, cache writes (`cache_creation`) at
    cache_write_price_per_1m, the remainder of input tokens at input_price_per_1m. Output tokens (reasoning included) at output_price_per_1m.
    This is the FALLBACK: when OpenRouter reports `provider_cost_usd` (real upstream cost)
    the usage repository prefers it.
    """
    if not usage:
        return 0.0
    in_det = usage.get("input_token_details") or {}
    cached = int(in_det.get("cache_read") or 0)
    created = int(in_det.get("cache_creation") or 0) if cfg.cache_write_price_per_1m else 0
    fresh_input = max(int(usage.get("input_tokens") or 0) - cached - created, 0)
    output = int(usage.get("output_tokens") or 0)
    raw = (
        fresh_input * cfg.input_price_per_1m
        + cached * cfg.cached_input_price_per_1m
        + created * cfg.cache_write_price_per_1m
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
        # Prices measured 2026-10-10 (USD per 1M): input 0.10, output 0.50, cache read 0.01,
        # cache write 0.125. Context 1M. Haiku's tokenizer yields ~1.6x more tokens than GLM's
        # for the same Portuguese text — compare COST, not token counts, across the two.
        CLAUDE_HAIKU_5_5 = ModelConfig(
            "anthropic/claude-haiku-5.5",
            "openrouter",
            # "low" is the WhatsApp sweet spot (see module docstring): medium+ blows the p90
            # latency. Anthropic ignores reasoning when a tool is forced, so
            # `complete_structured` stays cheap regardless.
            reasoning=True,
            reasoning_effort="low",
            input_price_per_1m=0.10,
            cached_input_price_per_1m=0.01,
            cache_write_price_per_1m=0.125,
            output_price_per_1m=0.50,
            prompt_cache_control=True,
            supports_image_input=True,
            # OpenRouter input modalities for Haiku 5.5: text, image, file (PDF). No video, no
            # audio. Video is handled as sampled frames in `media.py`; audio is Whisper-or-nothing.
            supports_video_input=False,
            supports_audio_input=False,
            # Haiku DOES accept PDF inline, but we keep the proven MarkItDown / page-OCR path
            # (`ocr.py`). Flipping this flag re-enables the inline `file` branch of `media.py` —
            # do it as a separate, tested decision (cost and fidelity on scanned PDFs untested).
            supports_pdf_input=False,
            # `allow_fallbacks=False` + this order is a JURISDICTION statement, not a price one.
            # This model talks to end customers and summarizes whole transcripts; every upstream
            # below is US-based, and that is what privacy policies and the Meta App Review Data
            # Handling answer declare. With fallbacks on, a 429 silently reroutes to ANY upstream
            # of the slug and those declarations become false with no signal. Three in line make a
            # 429 reroute INSIDE the list instead of becoming an error. All three tested OK on
            # 2026-10-10; the regional bedrock/vertex variants cost ~10% more, so they are
            # backstops, with Anthropic first.
            #
            # CAVEAT: OpenRouter's endpoint metadata (`GET /api/v1/models/<slug>/endpoints`)
            # reports `supports_tool_choice.required=false/function=false` for EVERY Haiku
            # upstream, yet forced tool calls (`with_structured_output(method="function_calling")`
            # and `bind_tools(tool_choice="any")`) work on anthropic and amazon-bedrock — the
            # metadata is wrong for this model. Before reordering or adding an upstream, probe it
            # with a REAL forced-tool call, do not trust the metadata flag.
            provider_order=("anthropic", "amazon-bedrock/us-east-1", "google-vertex/us"),
            allow_provider_fallbacks=False,
        )

        # NOT a chat model — audio transcription only, orders of magnitude cheaper than sending
        # audio to a multimodal model. It lives here so cost accounting finds its provider/
        # model_id; the call is a JSON POST to OpenRouter's STT endpoint in `media.py` (not
        # OpenAI-chat-compatible, does not fit `init_model`). Billed per SECOND of audio and the
        # response carries the real cost, so token prices stay zero on purpose. Upstreams
        # (DeepInfra cheapest, Groq fallback) are both US-based.
        WHISPER_LARGE_V3_TURBO = ModelConfig(
            "openai/whisper-large-v3-turbo",
            "openrouter",
            supports_audio_input=True,
            is_chat_model=False,
        )

        # NOT a chat model — text-to-speech only (`core/agents/speech.py`, POST `/audio/speech`,
        # mp3 out, voice cloning by `input_references`). Chosen 2026-10-23 by a blind listening
        # test against Gemini Flash TTS, Fish S2.1, HeyGen and Seed. `input_price_per_1m` is per
        # 1M CHARACTERS of `input` + `instructions` (OpenRouter pricing "prompt" 0.000002, checked
        # against 4 real generations: the voice-reference transcript is NOT billed). This price IS
        # what gets billed: the reported cost (`GET /generation`) only shows up ~11 s after the
        # audio, too late for callers with someone waiting — see `speech.py`.
        FISH_AUDIO_DRAMA_3 = ModelConfig(
            "fish-audio/drama-3",
            "openrouter",
            input_price_per_1m=2.0,
            is_chat_model=False,
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
    """Lookup by model_id alone — what tenant configs and yaml persist (e.g. "anthropic/claude-haiku-5.5")."""
    for config in iter_model_configs():
        if config.model_id == model_id:
            return config
    return None
