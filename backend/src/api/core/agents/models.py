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
    # Capabilities — usadas pelo frontend para bloquear uploads incompatíveis
    # (texto/documento sempre suportado via MarkItDown — sem flag).
    supports_image_input: bool = False
    supports_pdf_input: bool = False  # PDF nativo (sem MarkItDown)
    supports_audio_input: bool = False
    supports_video_input: bool = False
    # OpenRouter provider routing (ignorado pelos demais provedores): ordem de upstreams
    # preferidos. allow_provider_fallbacks=False fixa no primeiro que responder de
    # `provider_order` (429 do upstream vira erro em vez de reroute).
    provider_order: tuple[str, ...] = ()
    allow_provider_fallbacks: bool = True


def model_capabilities_dict(cfg: "ModelConfig") -> dict[str, bool]:
    """Snapshot serializável das flags de capacidade para o /agents endpoint."""
    return {
        "image_input": cfg.supports_image_input,
        "pdf_input": cfg.supports_pdf_input,
        "audio_input": cfg.supports_audio_input,
        "video_input": cfg.supports_video_input,
        "reasoning": cfg.reasoning or cfg.thinking,
    }


def round_cost_up(value: float) -> float:
    """Round a USD amount UP to COST_DECIMAL_PLACES (never under-bills)."""
    return math.ceil(value * COST_SCALE) / COST_SCALE


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
    return round_cost_up(raw)


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
    "chat_deepseek": "deepseek",
    "chat_openrouter": "openrouter",
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


def find_model_config_by_id(model_id: str) -> ModelConfig | None:
    """Lookup a ModelConfig by model_id alone (provider-agnostic).

    The org-configurable attendant stores only a model_id (e.g. "deepseek-v4-flash");
    this resolves it to the full config so the dispatcher can instantiate it.
    """
    for namespace in vars(Models).values():
        if not isinstance(namespace, type):
            continue
        for value in vars(namespace).values():
            if isinstance(value, ModelConfig) and value.model_id == model_id:
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
            supports_image_input=True,
            supports_pdf_input=True,
            supports_audio_input=True,
            supports_video_input=True,
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
            supports_image_input=True,
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
        # Transcrição de áudio (ver `core/agents/media.py`). NÃO é chat model: não passa por
        # `init_model` e é cobrado por HORA DE ÁUDIO, não por token — por isso os campos de
        # preço ficam zerados aqui e a conta sai de `WHISPER_USD_PER_HOUR`. Substituiu o
        # `LLAMA_4_SCOUT`, que estava registrado sem preço nenhum e nunca era referenciado:
        # modelo sem preço no registro lê custo ZERO em silêncio, e o teto de gasto some.
        WHISPER_LARGE_V3_TURBO = ModelConfig(
            "whisper-large-v3-turbo",
            "groq",
            supports_audio_input=True,
        )

    class DeepSeek:
        # Modelos atuais (substituem deepseek-chat / deepseek-reasoner):
        # ambos suportam tool calling, JSON output e reasoning (thinking mode).
        # Pricing oficial: https://api-docs.deepseek.com/quick_start/pricing
        # Context: 1M tokens · max output: 384K tokens.
        V4_FLASH = ModelConfig(
            "deepseek-v4-flash",
            "deepseek",
            reasoning=True,
            reasoning_effort="high",
            input_price_per_1m=0.14,
            cached_input_price_per_1m=0.0028,
            output_price_per_1m=0.28,
        )
        # V4 Pro: pricing reflete desconto de 75% válido até 2026-05-31.
        V4_PRO = ModelConfig(
            "deepseek-v4-pro",
            "deepseek",
            reasoning=True,
            reasoning_effort="high",
            input_price_per_1m=0.435,
            cached_input_price_per_1m=0.003625,
            output_price_per_1m=0.87,
        )

    class OpenRouter:
        # Gateway multi-provider (API OpenAI-compatible). `model_id` é o slug do OpenRouter e
        # `provider_order` fixa o upstream preferido — o mesmo modelo é servido por dezenas de
        # provedores com preço/latência diferentes. O pricing abaixo é o do upstream preferido
        # (fallback do cálculo); quando o OpenRouter reporta `usage.cost`, a contabilização usa
        # o valor REAL cobrado pelo upstream roteado (ver repositories/agents/usage.py).
        # Preços: https://openrouter.ai/deepseek/deepseek-v4-flash-0731
        DEEPSEEK_V4_FLASH_0731 = ModelConfig(
            "deepseek/deepseek-v4-flash-0731",
            "openrouter",
            reasoning=True,
            reasoning_effort="high",
            input_price_per_1m=0.14,
            cached_input_price_per_1m=0.028,
            output_price_per_1m=0.28,
            provider_order=("novita",),
            allow_provider_fallbacks=True,
        )
        # Os olhos e os ouvidos de um atendente text-only. Áudio, imagem, vídeo e PDF viram
        # texto aqui antes de entrar no prompt dele (ver `core/agents/media.py`). Pelo
        # OpenRouter de propósito: reusa o `ChatOpenRouter` que já existe, não custa
        # dependência nova e o custo cai em `agent_message_usage` pelo `usage_recorder` de
        # sempre — sem uma linha de contabilidade nova.
        GEMINI_3_7_FLASH = ModelConfig(
            "google/gemini-3.7-flash",
            "openrouter",
            thinking=True,
            input_price_per_1m=0.375,
            cached_input_price_per_1m=0.0375,
            output_price_per_1m=1.875,
            supports_image_input=True,
            supports_pdf_input=True,
            supports_audio_input=True,
            supports_video_input=True,
        )

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
