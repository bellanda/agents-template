from pathlib import Path
from typing import Any

from asyncpg.connection import Connection
from fastapi import APIRouter, Depends, HTTPException

from api.core.exceptions import ForbiddenError
from api.repositories.agents.chat_history import (
    delete_chat,
    get_chat_messages,
    get_chat_owner,
    get_user_threads,
)
from api.repositories.uploads.user_upload_repository import user_upload_repository
from api.routes.uploads import CHAT_DOMAIN, CHAT_THREADS_SUB, ENTITY_CHAT_SESSION
from api.services.auth import get_auth_context
from config.database import get_conn
from config.uploads import USERS, delete_directory

router = APIRouter()


def _safe_segment(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = Path(value).name
    if not cleaned or cleaned in ("..", "."):
        return None
    return cleaned


async def _purge_thread_uploads(conn: Connection, user_id: str, thread_id: str) -> None:
    """Remove the thread's upload tree on disk AND its ``user_uploads`` rows.

    Disk layout: ``users/<user>/chat/threads/<thread>/`` (see routes/uploads.py).
    No FK cascade links chat_history → user_uploads, so we soft-delete the rows
    explicitly here. Idempotent.
    """
    safe_user = _safe_segment(user_id)
    safe_thread = _safe_segment(thread_id)
    if not safe_user or not safe_thread:
        return

    rows = await user_upload_repository.find_by_entity(conn, ENTITY_CHAT_SESSION, safe_thread)
    for row in rows:
        await user_upload_repository.soft_delete(conn, row["id"])

    await delete_directory(USERS, safe_user, CHAT_DOMAIN, CHAT_THREADS_SUB, safe_thread)


@router.get("/threads")
async def list_threads(
    agent_id: str | None = None,
    ctx: dict = Depends(get_auth_context),
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    """List all conversation threads for the authenticated user."""
    threads = await get_user_threads(conn, ctx["user_id"])
    if agent_id:
        threads = [t for t in threads if t.get("agent_id") == agent_id]

    return {"threads": threads}


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    ctx: dict = Depends(get_auth_context),
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    """Get the message history for a specific thread (owner-scoped)."""
    owner = await get_chat_owner(conn, thread_id)
    if owner is not None and owner[0] != ctx["user_id"]:
        raise ForbiddenError(detail="Thread belongs to another user")

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
async def delete_thread(
    thread_id: str,
    ctx: dict = Depends(get_auth_context),
    conn: Connection = Depends(get_conn),
) -> dict[str, str]:
    owner = await get_chat_owner(conn, thread_id)
    if owner is not None and owner[0] != ctx["user_id"]:
        raise ForbiddenError(detail="Thread belongs to another user")
    deleted = await delete_chat(conn, thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")
    if owner is not None:
        user_id, owned_thread_id = owner
        await _purge_thread_uploads(conn, user_id, owned_thread_id)
    return {"status": "deleted", "thread_id": thread_id}
