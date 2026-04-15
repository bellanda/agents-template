from typing import Any

from asyncpg.connection import Connection
from fastapi import APIRouter, Depends, HTTPException

from api.repositories.agents.chat_history import delete_chat, get_chat_messages, get_user_threads
from config.database import get_conn

router = APIRouter()


@router.get("/threads")
async def list_threads(
    agent_id: str | None = None,
    user_id: str | None = None,
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    """List all conversation threads for a user."""
    if not user_id:
        return {"threads": []}

    threads = await get_user_threads(conn, user_id)
    if agent_id:
        threads = [t for t in threads if t.get("agent_id") == agent_id]

    return {"threads": threads}


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    """Get the message history for a specific thread."""
    messages = await get_chat_messages(conn, thread_id)

    if not messages:
        return {"thread_id": thread_id, "messages": []}

    serialized_messages = []
    for idx, msg in enumerate(messages):
        try:
            role = msg.get("role")
            content = msg.get("content", "")
            parts = msg.get("parts")

            if role in ("human", "user"):
                role = "user"
            elif role in ("ai", "assistant"):
                role = "assistant"
            else:
                continue

            if not content and not parts:
                continue

            msg_data: dict[str, Any] = {
                "role": role,
                "content": content,
                "id": msg.get("id") or f"{role}-{idx}",
            }
            if msg.get("reasoning"):
                msg_data["reasoning"] = msg.get("reasoning")
            if isinstance(parts, list) and parts:
                msg_data["parts"] = parts

            serialized_messages.append(msg_data)
        except Exception:
            continue

    return {"thread_id": thread_id, "messages": serialized_messages}


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str, conn: Connection = Depends(get_conn)) -> dict[str, str]:
    deleted = await delete_chat(conn, thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")
    return {"status": "deleted", "thread_id": thread_id}
