from typing import Any


def _reasoning_summary_text_from_block(block: dict) -> str:
    """Text from a single Gemini/OpenAI-style reasoning content block."""
    bt = block.get("type")
    if bt == "thinking" and isinstance(block.get("thinking"), str):
        return block["thinking"]
    if bt == "reasoning":
        if isinstance(block.get("reasoning"), str):
            return block["reasoning"]
        summary = block.get("summary")
        if isinstance(summary, list):
            parts: list[str] = []
            for item in summary:
                if isinstance(item, dict) and item.get("type") == "summary_text":
                    t = item.get("text")
                    if isinstance(t, str):
                        parts.append(t)
            return "".join(parts)
    return ""


def extract_thinking_from_content(content: Any) -> str:
    """Gemini / OpenAI Responses reasoning blocks in message content."""
    if content is None or isinstance(content, str):
        return ""
    if isinstance(content, dict):
        return _reasoning_summary_text_from_block(content)
    if isinstance(content, list):
        return "".join(
            _reasoning_summary_text_from_block(block)
            for block in content
            if isinstance(block, dict)
        )
    return ""


def reasoning_from_additional_kwargs(additional: dict) -> str:
    """OpenAI v0 stores reasoning on additional_kwargs; merge with streamed content."""
    if not additional:
        return ""
    rc = additional.get("reasoning_content")
    if isinstance(rc, str) and rc:
        return rc
    r = additional.get("reasoning")
    if isinstance(r, dict):
        return _reasoning_summary_text_from_block(r)
    if isinstance(r, str):
        return r
    return ""


def normalize_chunk_text(content: Any) -> str:
    """Visible assistant text (OpenAI: str; Gemini: list blocks excluding thinking/reasoning)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                bt = block.get("type")
                if bt in ("thinking", "reasoning"):
                    continue
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
                else:
                    c = block.get("content")
                    if isinstance(c, str):
                        parts.append(c)
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def _extract_message_content(agent_response: Any) -> str:
    """Best-effort extraction of the final assistant content from LangGraph output."""
    if isinstance(agent_response, str):
        return agent_response

    if isinstance(agent_response, dict):
        messages = agent_response.get("messages") or agent_response.get("output")
        if messages:
            last = messages[-1]
            raw = (
                getattr(last, "content", None)
                if not isinstance(last, dict)
                else last.get("content")
            )
            if raw:
                return normalize_chunk_text(raw)
        return str(agent_response)

    return str(agent_response)


async def execute_agent(agent_info: dict, query: str, session_id: str) -> str:
    """Execute agent and return the final response."""
    agent = agent_info["agent"]

    config: dict = {"configurable": {"thread_id": session_id}}

    try:
        response = await agent.ainvoke(
            {"messages": [{"role": "user", "content": query}]},
            config=config,
        )
        return _extract_message_content(response)
    except Exception as e:
        return f"❌ Desculpe, ocorreu um erro inesperado: {e!s}"


async def call_agent_async(
    query: str, session_id: str, model_id: str, agents_registry: dict
) -> str:
    """Execute agent and return response."""
    if model_id not in agents_registry:
        available = list(agents_registry.keys())
        raise Exception(f"Model '{model_id}' not found. Available: {available}")

    agent_info = agents_registry[model_id]
    return await execute_agent(agent_info, query, session_id)
