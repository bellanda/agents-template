import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from config.paths import BASE_DIR

DB_PATH = BASE_DIR / "data" / "checkpoints.db"

# Shared checkpointer. We don't use from_conn_string() because it's an async
# context manager that closes on exit; we need a long-lived connection for the app.
checkpointer: AsyncSqliteSaver | None = None
_conn_cm: aiosqlite.Connection | None = None


async def init_checkpointer() -> AsyncSqliteSaver:
    """Initialize the async SQLite checkpointer (call once at app startup)."""
    global checkpointer, _conn_cm
    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn_cm = aiosqlite.connect(str(DB_PATH))
    conn = await _conn_cm.__aenter__()
    checkpointer = AsyncSqliteSaver(conn)
    await checkpointer.setup()
    return checkpointer


async def close_checkpointer() -> None:
    """Close the checkpointer connection (call at app shutdown)."""
    global checkpointer, _conn_cm
    if _conn_cm is not None:
        await _conn_cm.__aexit__(None, None, None)
        _conn_cm = None
    checkpointer = None


def get_checkpointer() -> AsyncSqliteSaver | None:
    """Return the current shared checkpointer instance."""
    return checkpointer
