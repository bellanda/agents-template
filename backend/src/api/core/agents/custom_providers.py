import os
from typing import Any

import dotenv
from langchain_cerebras import ChatCerebras
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_deepseek import ChatDeepSeek
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import ChatOpenAI

from api.core.agents.models import ModelConfig, find_model_config_by_id

dotenv.load_dotenv(override=True)


class ChatChutes(ChatOpenAI):
    """Custom class to extract reasoning_content from Chutes AI."""

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

        # Extract reasoning fields from the raw chunk
        choices = chunk.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            # Chutes sends 'reasoning' or 'reasoning_content'
            reasoning = delta.get("reasoning_content") or delta.get("reasoning")
            if reasoning:
                gen_chunk.message.additional_kwargs["reasoning_content"] = reasoning

        return gen_chunk


class ChatCerebrasCustom(ChatCerebras):
    """Custom class to extract reasoning_content from Cerebras AI."""

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        # Cerebras sends reasoning in delta.reasoning during streaming
        raw_reasoning = None
        choices = chunk.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            raw_reasoning = delta.get("reasoning")

        gen_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )

        if gen_chunk is None:
            return None

        reasoning = raw_reasoning or gen_chunk.message.additional_kwargs.get("reasoning")
        if reasoning:
            gen_chunk.message.additional_kwargs["reasoning_content"] = reasoning

        return gen_chunk


def init_chutes_model(
    model: str, streaming: bool = True, reasoning: bool = False, **kwargs: Any
) -> ChatChutes:
    """Initialize a Chutes model with reasoning support."""
    if reasoning:
        kwargs["extra_body"] = kwargs.get("extra_body", {})
        kwargs["extra_body"]["include_reasoning"] = True

    return ChatChutes(
        model=model,
        openai_api_base=os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1"),
        openai_api_key=os.getenv("CHUTES_API_KEY"),
        streaming=streaming,
        **kwargs,
    )


def init_cerebras_model(model: str, streaming: bool = True, **kwargs: Any) -> ChatCerebrasCustom:
    """Initialize a Cerebras model with reasoning support."""
    if "disable_reasoning" not in kwargs:
        kwargs["disable_reasoning"] = False

    return ChatCerebrasCustom(
        model=model,
        api_key=os.getenv("CEREBRAS_API_KEY"),
        streaming=streaming,
        **kwargs,
    )


def init_google_model(
    model: str,
    streaming: bool = True,
    *,
    include_thoughts: bool | None = None,
    **kwargs: Any,
) -> ChatGoogleGenerativeAI:
    """Gemini thinking models need ``include_thoughts=True`` to stream thought blocks."""
    params: dict[str, Any] = {
        "model": model,
        "google_api_key": os.getenv("GOOGLE_API_KEY"),
        "streaming": streaming,
        **kwargs,
    }
    if include_thoughts is not None:
        params["include_thoughts"] = include_thoughts
    if include_thoughts is True and params.get("thinking_level") is None:
        params["thinking_level"] = "high"
    return ChatGoogleGenerativeAI(**params)


def init_groq_model(model: str, streaming: bool = True, **kwargs: Any) -> ChatGroq:
    return ChatGroq(
        model=model,
        groq_api_key=os.getenv("GROQ_API_KEY"),
        streaming=streaming,
        **kwargs,
    )


def init_nvidia_model(
    model: str, thinking: bool = False, max_tokens: int = 16384, **kwargs: Any
) -> ChatNVIDIA:
    """Initialize NVIDIA model with optional thinking support.

    NVIDIA chat/completions expects ``chat_template_kwargs`` on the request body
    (see integrate.api.nvidia.com). LangChain's ChatNVIDIA merges ``model_kwargs``
    into that payload — do not use ``extra_body`` (it is not a ChatNVIDIA field
    and triggers a LangChain warning).
    """
    model_kwargs: dict[str, Any] = dict(kwargs.pop("model_kwargs", None) or {})
    model_kwargs["stream"] = True
    if thinking:
        model_kwargs["chat_template_kwargs"] = {"enable_thinking": True}

    return ChatNVIDIA(
        model=model,
        nvidia_api_key=os.getenv("NVIDIA_API_KEY"),
        max_tokens=max_tokens,
        model_kwargs=model_kwargs,
        **kwargs,
    )


class ChatDeepSeekRoundtrip(ChatDeepSeek):
    """ChatDeepSeek que devolve `reasoning_content` no payload da próxima call.

    DeepSeek V4 em thinking mode exige que o `reasoning_content` da AIMessage
    anterior seja reincluído na request seguinte — caso contrário a API responde
    400 ``"The reasoning_content in the thinking mode must be passed back to
    the API."``. O ChatDeepSeek base de langchain-deepseek 1.0.1 não faz esse
    round-trip; aqui reinjetamos a partir de ``additional_kwargs``.
    """

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)

        source_messages: list[Any] = []
        if hasattr(input_, "to_messages"):
            source_messages = list(input_.to_messages())
        elif isinstance(input_, list):
            source_messages = list(input_)

        src_iter = iter(source_messages)
        for out_msg in payload.get("messages", []):
            if out_msg.get("role") != "assistant":
                continue
            src_msg = None
            for candidate in src_iter:
                if getattr(candidate, "type", None) == "ai":
                    src_msg = candidate
                    break
            if src_msg is None:
                break
            extras = getattr(src_msg, "additional_kwargs", None) or {}
            reasoning = extras.get("reasoning_content")
            if reasoning:
                out_msg["reasoning_content"] = reasoning

        return payload


def init_deepseek_model(
    model: str,
    streaming: bool = True,
    *,
    reasoning_effort: str | None = None,
    **kwargs: Any,
) -> ChatDeepSeekRoundtrip:
    """Initialize a DeepSeek model via langchain-deepseek (with reasoning round-trip).

    `reasoning_effort` (low | high | max) is sent in the OpenAI-compatible request
    body — DeepSeek V4 reads it from there.
    """
    if reasoning_effort is not None:
        kwargs["extra_body"] = {
            **kwargs.pop("extra_body", {}),
            "reasoning_effort": reasoning_effort,
        }
    return ChatDeepSeekRoundtrip(
        model=model,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        streaming=streaming,
        **kwargs,
    )


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


def init_openai_model(
    model: str,
    streaming: bool = True,
    *,
    reasoning: bool = False,
    reasoning_effort: str | None = None,
    **kwargs: Any,
) -> ChatOpenAI:
    """OpenAI GPT-5 family reasoning uses the Responses API (LangChain routes via ``reasoning``)."""
    effort = reasoning_effort if reasoning_effort is not None else ("xhigh" if reasoning else None)
    params: dict[str, Any] = {
        "model": model,
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "streaming": streaming,
        **kwargs,
    }
    # Responses API only surfaces reasoning to the client when ``summary`` is set (e.g. auto).
    if effort:
        params["reasoning"] = {"effort": effort, "summary": "auto"}
    return ChatOpenAI(**params)


def init_model(config: ModelConfig, **overrides: Any) -> BaseChatModel:
    """Instantiate a LangChain model from a ModelConfig with optional parameter overrides.

    Config defaults (reasoning, thinking) are used unless explicitly overridden.

    Examples:
        init_model(Models.Groq.KIMI_K2_INSTRUCT)
        init_model(Models.Chutes.GPT_OSS_120B_TEE, max_tokens=16384)
        init_model(Models.NVIDIA.DEEPSEEK_V3_2, thinking=False)
    """
    match config.provider:
        case "chutes":
            reasoning = overrides.pop("reasoning", config.reasoning)
            return init_chutes_model(config.model_id, reasoning=reasoning, **overrides)
        case "cerebras":
            return init_cerebras_model(config.model_id, **overrides)
        case "deepseek":
            reasoning_effort = overrides.pop("reasoning_effort", config.reasoning_effort)
            return init_deepseek_model(
                config.model_id,
                reasoning_effort=reasoning_effort,
                **overrides,
            )
        case "google":
            thinking = overrides.pop("thinking", config.thinking)
            include_thoughts = overrides.pop("include_thoughts", True if thinking else None)
            if "max_tokens" in overrides:
                overrides["max_output_tokens"] = overrides.pop("max_tokens")
            return init_google_model(
                config.model_id,
                include_thoughts=include_thoughts,
                **overrides,
            )
        case "groq":
            return init_groq_model(config.model_id, **overrides)
        case "nvidia":
            thinking = overrides.pop("thinking", config.thinking)
            return init_nvidia_model(config.model_id, thinking=thinking, **overrides)
        case "openrouter":
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
        case "openai":
            reasoning = overrides.pop("reasoning", config.reasoning)
            reasoning_effort = overrides.pop("reasoning_effort", config.reasoning_effort)
            return init_openai_model(
                config.model_id,
                reasoning=reasoning,
                reasoning_effort=reasoning_effort,
                **overrides,
            )
        case _:
            raise ValueError(f"Unknown provider: {config.provider!r}")


def init_model_by_id(model_id: str, **overrides: Any) -> BaseChatModel:
    """Resolve a registered model_id to a live LangChain model.

    Raises ValueError if the id is not in the Models registry — the org-config
    layer must only persist ids that exist here.
    """
    config = find_model_config_by_id(model_id)
    if config is None:
        raise ValueError(f"Unknown model_id: {model_id!r}. Not registered in Models.")
    return init_model(config, **overrides)
