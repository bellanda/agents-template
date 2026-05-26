import os
from typing import Any

import dotenv
from langchain_cerebras import ChatCerebras
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGenerationChunk
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
