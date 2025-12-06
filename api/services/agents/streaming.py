import json
from typing import Dict

from api.services.agents.tools import (
    generate_result_message,
    generate_status_message,
    generate_tool_end_message,
    generate_tool_start_message,
)


def _chunk(completion_id: str, requested_model: str, current_timestamp: int, content: str) -> str:
    """Build a SSE/OpenAI-compatible chunk string."""
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": current_timestamp,
        "model": requested_model,
        "choices": [{"index": 0, "delta": {"content": content}, "logprobs": None, "finish_reason": None}],
    }
    return f"data: {json.dumps(payload)}\n\n"


async def stream_langchain_agent(
    agent_info: Dict,
    query: str,
    user_id: str,
    session_id: str,
    completion_id: str,
    current_timestamp: int,
    requested_model: str,
    verbose: bool = False,
):
    """Stream LangChain/LangGraph events with lightweight, user-facing updates."""
    agent = agent_info["agent"]  # AgentExecutor / LangGraph app

    try:
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": query}]},
            version="v1",
            config={"configurable": {"thread_id": session_id}},
        ):
            event_type = event.get("event")

            if event_type == "on_chain_start" and verbose:
                status_msg = generate_status_message("processing", "Analisando solicitação...")
                yield _chunk(completion_id, requested_model, current_timestamp, f"\n{status_msg}\n")

            elif event_type == "on_tool_start":
                tool_name = event.get("name", "ferramenta")
                tool_input = event.get("data", {}).get("input", {})
                msg = generate_tool_start_message(tool_name, tool_input)
                yield _chunk(completion_id, requested_model, current_timestamp, f"\n{msg}\n")

            elif event_type == "on_tool_end":
                tool_name = event.get("name", "ferramenta")
                msg = generate_tool_end_message(tool_name)
                yield _chunk(completion_id, requested_model, current_timestamp, f"\n{msg}\n")

            elif event_type == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                content = getattr(chunk, "content", None)
                if content:
                    yield _chunk(completion_id, requested_model, current_timestamp, content)

            elif event_type == "on_chain_end" and verbose:
                done_msg = generate_result_message("success", "Resposta gerada com sucesso")
                yield _chunk(completion_id, requested_model, current_timestamp, f"\n{done_msg}\n")
            # Ignore other events to keep the stream lean
    except Exception as e:
        error_msg = f"❌ Streaming error: {str(e)}"
        yield _chunk(completion_id, requested_model, current_timestamp, error_msg)
