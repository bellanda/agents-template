from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from config.database import database_config

checkpointer: AsyncPostgresSaver | None = None
_conn_cm: AsyncPostgresSaver | None = None


async def init_checkpointer() -> AsyncPostgresSaver:
    """Initialize the async Postgres checkpointer."""
    global checkpointer, _conn_cm
    _conn_cm = AsyncPostgresSaver.from_conn_string(database_config.POSTGRES_DATABASE_URI)
    checkpointer = await _conn_cm.__aenter__()

    return checkpointer


async def close_checkpointer() -> None:
    """Close the checkpointer connection."""
    global checkpointer, _conn_cm
    if _conn_cm is not None:
        await _conn_cm.__aexit__(None, None, None)
        _conn_cm = None
    checkpointer = None


def get_checkpointer() -> AsyncPostgresSaver | None:
    """Return the current shared checkpointer instance."""
    return checkpointer
