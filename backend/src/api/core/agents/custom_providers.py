import os
from typing import Any

import dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI

from api.core.agents.models import ModelConfig, find_model_config_by_id

dotenv.load_dotenv(override=True)


class ChatOpenRouter(ChatOpenAI):
    """OpenRouter (gateway OpenAI-compatible) — reasoning, upstream roteado e custo real.

    Três coisas que o ChatOpenAI base não entrega quando o endpoint é o OpenRouter:

    1. **reasoning**: chega em ``delta.reasoning`` (stream) / ``message.reasoning``
       (one-shot) e é descartado pelo parser da langchain-openai. Reemitimos em
       ``additional_kwargs["reasoning_content"]`` — mesmo contrato dos outros
       provedores com reasoning do registro (Chutes/Cerebras/DeepSeek).
    2. **model_provider**: o base grava ``"openai"`` fixo; sem reescrever para
       ``"openrouter"`` o ``find_model_config`` não acha o ModelConfig e o custo sai zero.
    3. **custo real**: com ``usage: {include: true}`` o OpenRouter devolve ``usage.cost``
       (o que o upstream roteado realmente cobrou) e o nome desse upstream. Como o
       roteamento é dinâmico, esse valor vale mais que a tabela estática de preços —
       expomos os dois em ``response_metadata`` para a contabilização preferir o real.
    """

    def _stamp_openrouter_metadata(self, target: dict, raw: dict) -> None:
        """Reescreve o provider e anexa custo/upstream reportados pelo OpenRouter."""
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

        # `upstream_provider`/`provider_cost_usd` só no chunk que carrega usage (o último):
        # o merge de response_metadata entre chunks concatena strings e recusa floats repetidos.
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

        # Mesma exclusão do ChatOpenAI base: `parsed` pode conter Pydantic arbitrário
        # de structured output e não interessa aqui (só lemos provider/usage/reasoning).
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

    `reasoning_effort` (low | medium | high) e o roteamento de provider viajam no
    `extra_body` — são extensões do OpenRouter sobre o schema da OpenAI. `usage.include`
    pede o custo real do upstream de volta na resposta.
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

    # Headers de atribuição (aparecem no ranking de apps do OpenRouter) — opcionais.
    attribution = {
        header: value
        for header, env in (
            ("HTTP-Referer", "OPENROUTER_SITE_URL"),
            ("X-Title", "OPENROUTER_APP_TITLE"),
        )
        if (value := os.getenv(env))
    }

    return ChatOpenRouter(
        model=model,
        openai_api_base=os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        streaming=streaming,
        stream_usage=True,
        extra_body=extra_body,
        default_headers=attribution or None,
        **kwargs,
    )


def init_model(config: ModelConfig, **overrides: Any) -> BaseChatModel:
    """Instantiate a LangChain model from a ModelConfig with optional parameter overrides.

    Config defaults (reasoning, reasoning_effort, roteamento de upstream) valem a menos
    que sobrescritos aqui.

    A stack inteira fala com o OpenRouter — é o gateway único de chat. `Models.Groq`
    existe no registro só como linha de preço para a transcrição de áudio, que é POST
    multipart em `core/agents/media.py` e nunca passa por aqui.

    Example:
        init_model(Models.OpenRouter.GLM_5_3_FLASH)
        init_model(Models.OpenRouter.GLM_5_3_FLASH, streaming=False)
    """
    if config.provider != "openrouter":
        raise ValueError(
            f"Provider {config.provider!r} não é instanciável: o único gateway de chat é o "
            f"OpenRouter. Model id: {config.model_id!r}"
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

    Raises ValueError if the id is not in the Models registry — the org-config
    layer must only persist ids that exist here.
    """
    config = find_model_config_by_id(model_id)
    if config is None:
        raise ValueError(f"Unknown model_id: {model_id!r}. Not registered in Models.")
    return init_model(config, **overrides)
