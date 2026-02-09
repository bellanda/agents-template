from typing import AsyncGenerator

import orjson

from api.services.agents.history import get_chat_messages, save_chat


def _chunk(type_name: str, id: str, delta: str = "") -> str:
    """Build a Vercel AI SDK Data Stream Protocol chunk."""
    payload: dict = {"type": type_name, "id": id}
    if delta:
        payload["delta"] = delta

    return f"data: {orjson.dumps(payload).decode('utf-8')}\n\n"


def _error_chunk(error_text: str) -> str:
    """Build an error chunk (uses errorText, not delta)."""
    payload = {"type": "error", "errorText": error_text}
    return f"data: {orjson.dumps(payload).decode('utf-8')}\n\n"


async def stream_agent(
    agent_info: dict,
    query: str,
    user_id: str,
    session_id: str,
    completion_id: str,
    current_timestamp: int,
    requested_model: str,
    verbose: bool = False,
) -> AsyncGenerator[str, None]:
    """Stream agent events - Vercel AI SDK Data Stream Protocol."""
    agent = agent_info["agent"]
    agent_mode = agent_info.get("mode", "single-shot")

    yield f"data: {orjson.dumps({'type': 'start', 'messageId': completion_id}).decode('utf-8')}\n\n"

    reasoning_started = False
    text_started = False

    # Track full response and reasoning for history saving
    full_response = ""
    full_reasoning = ""

    # Chat-mode agents use the checkpointer thread_id for memory persistence
    config: dict = {"configurable": {"thread_id": session_id}, "metadata": {"user_id": user_id, "agent_id": requested_model}}

    try:
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": query}]},
            version="v1",
            config=config,
        ):
            event_type = event.get("event")

            if event_type == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                content = getattr(chunk, "content", "")
                reasoning_content = chunk.additional_kwargs.get("reasoning_content", "")

                # Reasoning MUST come before text (SDK orders parts by first-seen start)
                if reasoning_content:
                    if not reasoning_started:
                        yield _chunk("reasoning-start", completion_id)
                        reasoning_started = True
                    yield _chunk("reasoning-delta", completion_id, reasoning_content)
                    full_reasoning += reasoning_content

                if content:
                    if not text_started:
                        yield _chunk("text-start", completion_id)
                        text_started = True
                    yield _chunk("text-delta", completion_id, content)
                    full_response += content

    except Exception as e:
        error_msg = f"❌ Streaming error: {str(e)}"
        yield _error_chunk(error_msg)
    finally:
        if reasoning_started:
            yield _chunk("reasoning-end", completion_id)
        if not text_started:
            yield _chunk("text-start", completion_id)
        yield _chunk("text-end", completion_id)

        # Save to history if in chat mode
        if agent_mode == "chat":
            try:
                # Get existing messages or start new list
                history = get_chat_messages(session_id)
                if not history:
                    history = []

                # Add current exchange
                history.append({"role": "user", "content": query})

                assistant_msg = {"role": "assistant", "content": full_response}
                if full_reasoning:
                    assistant_msg["reasoning"] = full_reasoning

                if full_response or full_reasoning:
                    history.append(assistant_msg)

                save_chat(session_id, user_id, requested_model, history)
            except Exception as e:
                print(f"⚠️ Error saving history: {e}")

        yield "data: " + orjson.dumps({"type": "finish"}).decode("utf-8") + "\n\n"
