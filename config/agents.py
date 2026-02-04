from typing import Any, Optional

from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI

from config import api_keys


class ChatChutes(ChatOpenAI):
    """Custom class to extract reasoning_content from Chutes AI."""

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: Optional[dict],
    ) -> Optional[ChatGenerationChunk]:
        # Call the original implementation
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


def init_chutes_model(model: str, streaming: bool = True, **kwargs: Any) -> ChatChutes:
    """Initialize a Chutes model with reasoning support."""
    return ChatChutes(
        model=model,
        openai_api_base="https://llm.chutes.ai/v1",
        openai_api_key=api_keys.CHUTES_API_KEY,
        streaming=streaming,
        **kwargs,
    )
