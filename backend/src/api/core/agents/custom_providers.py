import os
from typing import Any

from langchain_cerebras import ChatCerebras
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGenerationChunk
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import ChatOpenAI

from api.core.agents.models import ModelConfig


class ChatChutes(ChatOpenAI):
    """Custom class to extract reasoning_content from Chutes AI."""

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        gen_chunk = super()._convert_chunk_to_generation_chunk(chunk, default_chunk_class, base_generation_info)

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

        gen_chunk = super()._convert_chunk_to_generation_chunk(chunk, default_chunk_class, base_generation_info)

        if gen_chunk is None:
            return None

        reasoning = raw_reasoning or gen_chunk.message.additional_kwargs.get("reasoning")
        if reasoning:
            gen_chunk.message.additional_kwargs["reasoning_content"] = reasoning

        return gen_chunk


def init_chutes_model(model: str, streaming: bool = True, reasoning: bool = False, **kwargs: Any) -> ChatChutes:
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


def init_google_model(model: str, streaming: bool = True, **kwargs: Any) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        streaming=streaming,
        **kwargs,
    )


def init_groq_model(model: str, streaming: bool = True, **kwargs: Any) -> ChatGroq:
    return ChatGroq(
        model=model,
        groq_api_key=os.getenv("GROQ_API_KEY"),
        streaming=streaming,
        **kwargs,
    )


def init_nvidia_model(model: str, thinking: bool = False, max_tokens: int = 16384, **kwargs: Any) -> ChatNVIDIA:
    """Initialize NVIDIA model with optional thinking support."""
    if "model_kwargs" not in kwargs:
        kwargs["model_kwargs"] = {}
    kwargs["model_kwargs"]["streaming"] = True

    if thinking:
        kwargs["extra_body"] = kwargs.get("extra_body", {})
        kwargs["extra_body"]["chat_template_kwargs"] = {
            "enable_thinking": True,
            "clear_thinking": False,
        }

    return ChatNVIDIA(
        model=model,
        nvidia_api_key=os.getenv("NVIDIA_API_KEY"),
        max_tokens=max_tokens,
        **kwargs,
    )


def init_openai_model(model: str, streaming: bool = True, **kwargs: Any) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        streaming=streaming,
        **kwargs,
    )


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
        case "google":
            return init_google_model(config.model_id, **overrides)
        case "groq":
            return init_groq_model(config.model_id, **overrides)
        case "nvidia":
            thinking = overrides.pop("thinking", config.thinking)
            return init_nvidia_model(config.model_id, thinking=thinking, **overrides)
        case "openai":
            return init_openai_model(config.model_id, **overrides)
        case _:
            raise ValueError(f"Unknown provider: {config.provider!r}")
