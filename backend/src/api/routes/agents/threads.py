from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.services.agents.history import delete_chat, get_chat_messages, get_user_threads
from api.services.agents.registry import get_agents_registry

router = APIRouter()


@router.get("/threads")
async def list_threads(
    agent_id: str | None = None,
    user_id: str | None = None,
    agents_registry: dict = Depends(get_agents_registry),
) -> dict[str, Any]:
    """List all conversation threads for a user."""
    if not user_id:
        return {"threads": []}

    threads = get_user_threads(user_id)

    # Optional filtering by agent_id
    if agent_id:
        threads = [t for t in threads if t.get("agent_id") == agent_id]

    return {"threads": threads}


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    agents_registry: dict = Depends(get_agents_registry),
) -> dict[str, Any]:
    """Get the message history for a specific thread."""
    messages = get_chat_messages(thread_id)

    if not messages:
        # Check if it's a new thread (no history yet)
        return {"thread_id": thread_id, "messages": []}

    # Normalize messages for frontend
    serialized_messages = []
    for idx, msg in enumerate(messages):
        try:
            role = msg.get("role")
            content = msg.get("content", "")

            # Normalize role
            if role in ("human", "user"):
                role = "user"
            elif role in ("ai", "assistant"):
                role = "assistant"
            else:
                continue

            if not content:
                continue

            msg_data = {"role": role, "content": content, "id": msg.get("id") or f"{role}-{idx}"}
            if msg.get("reasoning"):
                msg_data["reasoning"] = msg.get("reasoning")

            serialized_messages.append(msg_data)
        except Exception:
            continue

    return {"thread_id": thread_id, "messages": serialized_messages}


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str) -> dict[str, str]:
    """Delete a chat thread."""
    try:
        delete_chat(thread_id)
        return {"status": "deleted", "thread_id": thread_id}
    except Exception as e:
        print(f"❌ Error deleting thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
