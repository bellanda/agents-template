from typing import Any

from asyncpg.connection import Connection

from api.models.agents.history import ChatHistoryThread


async def get_chat_messages(conn: Connection, thread_id: str) -> list[dict[str, Any]] | None:
    """Get messages for a specific thread."""
    row = await conn.fetchrow("SELECT messages FROM chat_history WHERE thread_id = $1", thread_id)
    return list(row["messages"] or []) if row else None


async def save_chat(conn: Connection, chat_history_thread: ChatHistoryThread) -> dict[str, Any]:
    """Save or update a chat thread. Receives Pydantic for validation, returns raw dict to confirm execution."""
    row = await conn.fetchrow(
        """
        INSERT INTO chat_history (thread_id, user_id, agent_id, messages, preview, updated_at)
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
        ON CONFLICT(thread_id) DO UPDATE SET
            messages = EXCLUDED.messages,
            preview = EXCLUDED.preview,
            updated_at = CURRENT_TIMESTAMP
        RETURNING thread_id, user_id, agent_id, messages, preview, updated_at
        """,
        chat_history_thread.thread_id,
        chat_history_thread.user_id,
        chat_history_thread.agent_id,
        chat_history_thread.messages,
        chat_history_thread.preview,
    )
    return dict(row)


async def get_user_threads(conn: Connection, user_id: str) -> list[dict[str, Any]]:
    """List all threads for a user."""
    rows = await conn.fetch(
        """
        SELECT thread_id, agent_id, preview, updated_at as created_at
        FROM chat_history
        WHERE user_id = $1
        ORDER BY updated_at DESC
        """,
        user_id,
    )
    return [dict(row) for row in rows]


async def delete_chat(conn: Connection, thread_id: str) -> bool:
    """Delete a chat thread."""
    result = await conn.fetchval("DELETE FROM chat_history WHERE thread_id = $1 RETURNING thread_id", thread_id)
    return bool(result)
