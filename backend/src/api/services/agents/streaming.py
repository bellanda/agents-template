from collections.abc import AsyncGenerator

import orjson
from asyncpg.connection import Connection

from api.models.agents.history import ChatHistoryThread
from api.repositories.agents.chat_history import get_chat_messages, save_chat

PREVIEW_LENGTH = 200


def _chunk(type_name: str, message_id: str, delta: str = "") -> str:
    """Build SSE chunk for Vercel AI SDK useChat (text/event-stream format)."""
    payload: dict = {"type": type_name, "id": message_id}
    if delta:
        payload["delta"] = delta
    return f"data: {orjson.dumps(payload).decode('utf-8')}\n\n"


def _error_chunk(error_text: str) -> str:
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
    conn: Connection | None,
) -> AsyncGenerator[str]:
    """Stream agent events - Vercel AI SDK Data Stream Protocol (SSE)."""
    agent = agent_info["agent"]
    save_to_db: bool = agent_info.get("save_to_db", True)

    yield f"data: {orjson.dumps({'type': 'start', 'messageId': completion_id}).decode('utf-8')}\n\n"

    reasoning_started = False
    text_started = False
    full_response = ""
    full_reasoning = ""

    langgraph_config: dict = {
        "configurable": {"thread_id": session_id},
        "metadata": {"user_id": user_id, "agent_id": requested_model},
    }

    try:
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": query}]},
            version="v1",
            config=langgraph_config,
        ):
            event_type = event.get("event")

            if event_type == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk is None:
                    continue
                content = getattr(chunk, "content", "") or ""
                additional = getattr(chunk, "additional_kwargs", None) or {}
                reasoning_content = additional.get("reasoning_content", "") or additional.get("reasoning", "") or ""

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
        yield _error_chunk(f"Streaming error: {e!s}")
    finally:
        if reasoning_started:
            yield _chunk("reasoning-end", completion_id)
        if not text_started:
            yield _chunk("text-start", completion_id)
        yield _chunk("text-end", completion_id)

        if save_to_db and conn:
            try:
                history = await get_chat_messages(conn, session_id) or []
                history.append({"role": "user", "content": query})

                assistant_msg: dict = {"role": "assistant", "content": full_response}
                if full_reasoning:
                    assistant_msg["reasoning"] = full_reasoning

                if full_response or full_reasoning:
                    history.append(assistant_msg)

                preview_content = full_response or full_reasoning
                thread = ChatHistoryThread(
                    thread_id=session_id,
                    user_id=user_id,
                    agent_id=requested_model,
                    messages=history,
                    preview=(preview_content[:PREVIEW_LENGTH] + "...")
                    if len(preview_content) > PREVIEW_LENGTH
                    else (preview_content or None),
                )
                await save_chat(conn, thread)
            except Exception:
                pass

        yield f"data: {orjson.dumps({'type': 'finish'}).decode('utf-8')}\n\n"
