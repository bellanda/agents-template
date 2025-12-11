import json
from typing import AsyncGenerator, Dict

from api.services.agents.tools import (
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


async def stream_agent(
    agent_info: Dict,
    query: str,
    user_id: str,
    session_id: str,
    completion_id: str,
    current_timestamp: int,
    requested_model: str,
    verbose: bool = False,
) -> AsyncGenerator[str, None]:
    """Stream agent events with XML-based UI updates."""
    agent = agent_info["agent"]

    try:
        # LangGraph/LangChain event stream
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": query}]},
            version="v1",
            config={"configurable": {"thread_id": session_id}},
        ):
            event_type = event.get("event")

            # 1. Chain Start (Processing)
            if event_type == "on_chain_start" and verbose:
                # Only show if it's the root chain or significant
                if event.get("name") == "LangGraph":
                    status_msg = generate_status_message("processing", "Analisando solicitação...")
                    yield _chunk(completion_id, requested_model, current_timestamp, status_msg)

            # 2. Tool Start
            elif event_type == "on_tool_start":
                tool_name = event.get("name", "ferramenta")
                tool_input = event.get("data", {}).get("input", {})
                msg = generate_tool_start_message(tool_name, tool_input)
                yield _chunk(completion_id, requested_model, current_timestamp, msg)

            # 3. Tool End
            elif event_type == "on_tool_end":
                tool_name = event.get("name", "ferramenta")
                msg = generate_tool_end_message(tool_name, success=True)  # Assuming success if no exception raised yet
                yield _chunk(completion_id, requested_model, current_timestamp, msg)

            # 4. Content Streaming
            elif event_type == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                content = getattr(chunk, "content", None)
                if content:
                    yield _chunk(completion_id, requested_model, current_timestamp, content)

            # 5. Chain End
            elif event_type == "on_chain_end" and verbose:
                # Optional: Only needed if we want to signal explicit completion before [DONE]
                pass

    except Exception as e:
        error_msg = f"❌ Streaming error: {str(e)}"
        yield _chunk(completion_id, requested_model, current_timestamp, error_msg)
