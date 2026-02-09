import sqlite3

import orjson

from config.paths import BASE_DIR

DB_PATH = BASE_DIR / "data" / "history.db"


def init_db():
    """Initialize the simple history database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Simple table for chat history
    # thread_id: unique session ID
    # user_id: owner of the chat
    # agent_id: which agent was used
    # messages: JSON blob of the conversation
    # preview: short text for sidebar
    # updated_at: for sorting
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            thread_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            messages TEXT NOT NULL,
            preview TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Index for fast filtering by user
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON chat_history(user_id)")

    conn.commit()
    conn.close()


def save_chat(thread_id: str, user_id: str, agent_id: str, messages: list):
    """Save or update a chat thread."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Generate preview from first human message
    preview = ""
    for msg in messages:
        if msg.get("role") in ("user", "human"):
            preview = str(msg.get("content", ""))[:100]
            break

    messages_json = orjson.dumps(messages).decode("utf-8")

    cursor.execute(
        """
        INSERT INTO chat_history (thread_id, user_id, agent_id, messages, preview, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(thread_id) DO UPDATE SET
            messages = excluded.messages,
            preview = excluded.preview,
            updated_at = CURRENT_TIMESTAMP
    """,
        (thread_id, user_id, agent_id, messages_json, preview),
    )

    conn.commit()
    conn.close()


def get_user_threads(user_id: str):
    """List all threads for a user."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT thread_id, agent_id, preview, updated_at as created_at
        FROM chat_history
        WHERE user_id = ?
        ORDER BY updated_at DESC
    """,
        (user_id,),
    )

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_chat_messages(thread_id: str):
    """Get messages for a specific thread."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("SELECT messages FROM chat_history WHERE thread_id = ?", (thread_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return orjson.loads(row[0])
    return []


def delete_chat(thread_id: str):
    """Delete a chat thread."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE thread_id = ?", (thread_id,))
    conn.commit()
    conn.close()
