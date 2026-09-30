from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI

from api.core.agents.models import ModelConfig, find_model_config_by_id
from config.integrations import integrations_config


class ChatOpenRouter(ChatOpenAI):
    """OpenRouter (OpenAI-compatible gateway) — reasoning, routed upstream and real cost.

    Three things the base ChatOpenAI does not deliver when the endpoint is OpenRouter:

    1. **reasoning** arrives in ``delta.reasoning`` (stream) / ``message.reasoning``
       (one-shot) and is dropped by langchain-openai's parser. We re-emit it in
       ``additional_kwargs["reasoning_content"]`` — the single reasoning contract that
       ``services/agents/streaming.py`` consumes.
    2. **model_provider** is stamped as ``"openai"``; without rewriting it to
       ``"openrouter"`` ``find_model_config`` misses and the cost is recorded as zero.
    3. **real cost**: with ``usage: {include: true}`` OpenRouter returns ``usage.cost``
       (what the routed upstream actually charged) and that upstream's name. Routing is
       dynamic, so this beats the static price table — both go to ``response_metadata``
       and the usage repository prefers the real one.
    """

    def _stamp_openrouter_metadata(self, target: dict, raw: dict) -> None:
        """Rewrite the provider and attach the cost/upstream reported by OpenRouter."""
        target["model_provider"] = "openrouter"
        upstream = raw.get("provider")
        if upstream:
            target["upstream_provider"] = upstream
        cost = (raw.get("usage") or {}).get("cost")
        if cost is not None:
            target["provider_cost_usd"] = float(cost)

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        gen_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )

        if gen_chunk is None:
            return None

        choices = chunk.get("choices", [])
        if choices:
            delta = choices[0].get("delta") or {}
            reasoning = delta.get("reasoning_content") or delta.get("reasoning")
            if reasoning:
                gen_chunk.message.additional_kwargs["reasoning_content"] = reasoning

        # `upstream_provider`/`provider_cost_usd` only on the chunk that carries usage (the
        # last one): merging response_metadata across chunks concatenates strings and rejects
        # repeated floats.
        gen_chunk.message.response_metadata["model_provider"] = "openrouter"
        if chunk.get("usage"):
            self._stamp_openrouter_metadata(gen_chunk.message.response_metadata, chunk)

        return gen_chunk

    def _create_chat_result(
        self,
        response: dict | Any,
        generation_info: dict | None = None,
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)

        # Same exclusion as the base ChatOpenAI: `parsed` may hold arbitrary Pydantic from
        # structured output and is irrelevant here (we only read provider/usage/reasoning).
        raw = (
            response
            if isinstance(response, dict)
            else response.model_dump(exclude={"choices": {"__all__": {"message": {"parsed"}}}})
        )
        if result.llm_output is not None:
            self._stamp_openrouter_metadata(result.llm_output, raw)

        for generation, choice in zip(result.generations, raw.get("choices") or [], strict=False):
            message = (choice or {}).get("message") or {}
            reasoning = message.get("reasoning_content") or message.get("reasoning")
            if reasoning:
                generation.message.additional_kwargs["reasoning_content"] = reasoning

        return result


def init_openrouter_model(
    model: str,
    streaming: bool = True,
    *,
    reasoning: bool = False,
    reasoning_effort: str | None = None,
    provider_order: tuple[str, ...] = (),
    allow_provider_fallbacks: bool = True,
    **kwargs: Any,
) -> ChatOpenRouter:
    """Initialize an OpenRouter model (OpenAI-compatible endpoint).

    `reasoning_effort` (low | medium | high) and upstream routing travel in `extra_body` —
    they are OpenRouter extensions over the OpenAI schema. `usage.include` asks for the real
    upstream cost back in the response. Keys come from `settings` via `config/integrations.py`
    (SecretStr unwrapped there), never from `os.getenv` here.
    """
    extra_body: dict[str, Any] = {**kwargs.pop("extra_body", {}), "usage": {"include": True}}
    if reasoning_effort is not None:
        extra_body["reasoning"] = {"effort": reasoning_effort}
    elif reasoning:
        extra_body["reasoning"] = {"enabled": True}
    if provider_order:
        extra_body["provider"] = {
            "order": list(provider_order),
            "allow_fallbacks": allow_provider_fallbacks,
        }

    # Optional attribution headers (shown in OpenRouter's app ranking).
    attribution = {
        header: value
        for header, value in (
            ("HTTP-Referer", integrations_config.OPENROUTER_SITE_URL),
            ("X-Title", integrations_config.OPENROUTER_APP_TITLE),
        )
        if value
    }

    return ChatOpenRouter(
        model=model,
        openai_api_base=integrations_config.OPENROUTER_API_BASE,
        openai_api_key=integrations_config.OPENROUTER_API_KEY,
        streaming=streaming,
        stream_usage=True,
        extra_body=extra_body,
        default_headers=attribution or None,
        **kwargs,
    )


def init_model(config: ModelConfig, **overrides: Any) -> BaseChatModel:
    """Instantiate a LangChain model from a ModelConfig with optional parameter overrides.

    Config defaults (reasoning, reasoning_effort, upstream routing) apply unless overridden.

    The whole stack talks to OpenRouter — the single chat gateway. `Models.Groq` exists in
    the registry only as the price row for audio transcription, which is a multipart POST in
    `core/agents/media.py` and never goes through here.

    Example:
        init_model(Models.OpenRouter.GLM_5_3_FLASH)
        init_model(Models.OpenRouter.GLM_5_3_FLASH, streaming=False)
    """
    if config.provider != "openrouter":
        raise ValueError(
            f"Provider {config.provider!r} is not instantiable: OpenRouter is the only chat "
            f"gateway. Model id: {config.model_id!r}"
        )
    reasoning = overrides.pop("reasoning", config.reasoning)
    reasoning_effort = overrides.pop("reasoning_effort", config.reasoning_effort)
    return init_openrouter_model(
        config.model_id,
        reasoning=reasoning,
        reasoning_effort=reasoning_effort,
        provider_order=overrides.pop("provider_order", config.provider_order),
        allow_provider_fallbacks=overrides.pop(
            "allow_provider_fallbacks", config.allow_provider_fallbacks
        ),
        **overrides,
    )


def init_model_by_id(model_id: str, **overrides: Any) -> BaseChatModel:
    """Resolve a registered model_id to a live LangChain model.

    Raises ValueError if the id is not in the Models registry — tenant configs must only
    persist ids from `model_catalog.py`.
    """
    config = find_model_config_by_id(model_id)
    if config is None:
        raise ValueError(f"Unknown model_id: {model_id!r}. Not registered in Models.")
    return init_model(config, **overrides)
