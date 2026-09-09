import math
from dataclasses import dataclass
from typing import Any

COST_DECIMAL_PLACES = 6
COST_SCALE = 10**COST_DECIMAL_PLACES


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    provider: str
    # Liga o reasoning no upstream. `reasoning_effort` (low|medium|high) é mais
    # específico e vence quando os dois vêm preenchidos.
    reasoning: bool = False
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
        "reasoning": cfg.reasoning,
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
    "openai_chat": "openrouter",
    "openai_responses": "openrouter",
    "chat_openai": "openrouter",
    "chat_openrouter": "openrouter",
    "chat_groq": "groq",
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

    The org-configurable attendant stores only a model_id (e.g. "z-ai/glm-5.3-flash");
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
    """Model registry. Use init_model(Models.OpenRouter.NAME) in each agent to instantiate."""

    class OpenRouter:
        # Gateway multi-provider (API OpenAI-compatible) e ÚNICO caminho de chat da stack.
        # `model_id` é o slug do OpenRouter e `provider_order` fixa os upstreams aceitos —
        # o mesmo modelo é servido por dezenas de provedores com preço, quantização e
        # jurisdição diferentes. O pricing abaixo é o do primeiro da ordem (fallback do
        # cálculo); quando o OpenRouter reporta `usage.cost`, a contabilização usa o valor
        # REAL cobrado pelo upstream roteado.
        #
        # Multimodal nativo: o MESMO modelo conversa e lê a imagem que o usuário manda, e é
        # por isso que `media.py` não tem um "modelo de visão" próprio. As flags de
        # capacidade abaixo são o que liga/desliga cada ramo de `_content_parts` — trocar
        # de modelo aqui reconfigura o enriquecimento de mídia inteiro, sem tocar em media.py.
        GLM_5_3_FLASH = ModelConfig(
            "z-ai/glm-5.3-flash",
            "openrouter",
            reasoning=True,
            reasoning_effort="high",
            input_price_per_1m=0.15,
            output_price_per_1m=0.50,
            supports_image_input=True,
            supports_video_input=True,
            # GLM 5.3 Flash NÃO aceita PDF nem áudio inline (o catálogo do OpenRouter
            # declara text/image/video). Com isso o degrau "PDF/áudio → multimodal" fica
            # desligado: áudio é Whisper ou nada, e PDF não é enriquecido. Um modelo com
            # `file`/`audio` (ex.: google/gemini-3.8-flash) religa os dois só trocando
            # este bloco.
            supports_pdf_input=False,
            supports_audio_input=False,
            # `allow_fallbacks=False` + esta ordem é declaração de JURISDIÇÃO, não de preço:
            # os três upstreams são dos EUA. Com fallback ligado, um 429 reroteia em silêncio
            # para qualquer provedor do slug — inclusive a própria Z.AI, na China. Três em
            # fila faz o 429 rerotar DENTRO da jurisdição em vez de virar erro.
            #
            # A ordem não é por preço: CoreWeave e Fireworks servem em fp8, a DeepInfra em
            # fp4 — quantização mais agressiva castiga instruction-following e tool calling,
            # e a diferença entre o topo e o piso é US$ 0,075/M. BaseTen e a própria Z.AI
            # ficam FORA de propósito: nenhuma das duas serve `tool_choice: required`
            # neste modelo, e agente com ferramenta depende disso.
            provider_order=("coreweave", "fireworks", "deepinfra"),
            allow_provider_fallbacks=False,
        )

    class Groq:
        # NÃO é chat model — só transcrição de áudio. Existe aqui para a contabilidade achar
        # provider/model_id; a chamada é POST multipart em `media.py`, porque o endpoint de
        # transcrição não é OpenAI-chat-compatible e não cabe no `init_model`.
        # Cobrado por HORA de áudio, não por token — ver WHISPER_USD_PER_HOUR lá.
        WHISPER_LARGE_V3_TURBO = ModelConfig(
            "whisper-large-v3-turbo",
            "groq",
            supports_audio_input=True,
        )
