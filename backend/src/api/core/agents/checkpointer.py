"""LangGraph checkpointer lifecycle — asyncpg-backed, shares the app pool."""

from api.core.agents.asyncpg_saver import AsyncpgCheckpointSaver
from config.database import get_pool

checkpointer: AsyncpgCheckpointSaver | None = None


async def init_checkpointer() -> AsyncpgCheckpointSaver:
    """Bind the checkpointer to the app's asyncpg pool (already initialized)."""
    global checkpointer
    checkpointer = AsyncpgCheckpointSaver(await get_pool())
    return checkpointer


async def close_checkpointer() -> None:
    """Drop the reference; pool lifecycle is owned by close_asyncpg_pool()."""
    global checkpointer
    checkpointer = None


def get_checkpointer() -> AsyncpgCheckpointSaver | None:
    """Return the current shared checkpointer instance."""
    return checkpointer
