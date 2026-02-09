"""Provider-aware prompt caching utilities.

Prompt caching is a provider-level feature:
- OpenAI: automatic (nothing to do, prefixes are cached at 50% discount)
- Anthropic: explicit via cache_control markers on messages
- Groq/Chutes/NVIDIA: per-request pricing, no token cache benefit

This module provides utilities to detect when prompt caching can be applied
and a messages reducer for Anthropic incremental caching in conversations.
"""

from typing import Any


def is_anthropic_model(model: Any) -> bool:
    """Check if the model is an Anthropic ChatAnthropic instance."""
    model_class = type(model).__name__
    return model_class in ("ChatAnthropic", "ChatAnthropicMessages")


def is_openai_model(model: Any) -> bool:
    """Check if the model is an OpenAI model (caching is automatic)."""
    model_class = type(model).__name__
    return model_class in ("ChatOpenAI",)


def should_apply_prompt_cache(model: Any) -> bool:
    """Return True if explicit prompt caching markers are beneficial for this model.

    Only Anthropic models benefit from explicit cache_control markers.
    OpenAI handles caching automatically. Other providers (Groq, Chutes, NVIDIA)
    charge per-request so token-level caching doesn't apply.
    """
    return is_anthropic_model(model)


def apply_anthropic_cache_control(messages: list[dict]) -> list[dict]:
    """Mark the last message content block with cache_control for Anthropic incremental caching.

    This follows the pattern from the LangChain Anthropic docs:
    the longest previously-cached prefix is reused automatically by Claude.
    """
    if not messages:
        return messages

    # Walk backwards to find the last human message
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, list) and content:
                # Mark the last content block
                content[-1]["cache_control"] = {"type": "ephemeral"}
            elif isinstance(content, str):
                # Convert string to list format to add cache_control
                msg["content"] = [
                    {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}
                ]
            break

    return messages
