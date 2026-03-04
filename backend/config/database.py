from collections.abc import AsyncGenerator

import asyncpg
import orjson
from dotenv import load_dotenv

from config.tools import getenv_or_raise_exception

load_dotenv(override=True)


class DatabaseConfig:
    """PostgreSQL connection and pool configuration"""

    POSTGRES_DB: str = getenv_or_raise_exception("POSTGRES_DB")
    POSTGRES_USER: str = getenv_or_raise_exception("POSTGRES_USER")
    POSTGRES_PASSWORD: str = getenv_or_raise_exception("POSTGRES_PASSWORD")
    POSTGRES_HOST: str = getenv_or_raise_exception("POSTGRES_HOST")
    POSTGRES_PORT: str = getenv_or_raise_exception("POSTGRES_PORT")
    POSTGRES_DATABASE_URI: str = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

    POSTGRES_POOL_MIN_SIZE: int = int(getenv_or_raise_exception("POSTGRES_POOL_MIN_SIZE"))
    POSTGRES_POOL_MAX_SIZE: int = int(getenv_or_raise_exception("POSTGRES_POOL_MAX_SIZE"))
    POSTGRES_POOL_MAX_QUERIES: int = int(getenv_or_raise_exception("POSTGRES_POOL_MAX_QUERIES"))
    POSTGRES_POOL_MAX_INACTIVE_CONNECTION_LIFETIME: float = float(
        getenv_or_raise_exception("POSTGRES_POOL_MAX_INACTIVE_CONNECTION_LIFETIME")
    )
    POSTGRES_POOL_COMMAND_TIMEOUT: float = float(getenv_or_raise_exception("POSTGRES_POOL_COMMAND_TIMEOUT"))
    POSTGRES_POOL_TIMEOUT: float = float(getenv_or_raise_exception("POSTGRES_POOL_TIMEOUT"))


database_config = DatabaseConfig()

# ----------------------------------------------------------------------------
# 🛢️ DATABASE POOL MANAGEMENT
# ----------------------------------------------------------------------------

asyncpg_pool: asyncpg.Pool | None = None


async def init_connection(conn: asyncpg.Connection) -> None:
    """Configures JSON/JSONB codecs for every connection in the pool using orjson."""
    for type_name in ("json", "jsonb"):
        await conn.set_type_codec(
            type_name,
            schema="pg_catalog",
            encoder=lambda v: orjson.dumps(v).decode("utf-8"),
            decoder=orjson.loads,
            format="text",
        )


async def init_asyncpg_pool() -> None:
    """
    Initializes the asyncpg connection pool using DatabaseConfig.

    Includes advanced configurations for performance and stability:
    - min/max_size: Pool scaling boundaries
    - max_queries: Prevents memory leaks by recycling connections
    - max_inactive_connection_lifetime: Closes old idle connections
    - timeout: Connection establishment timeout
    - command_timeout: Default timeout for any single database command
    - init: Automatically configures type codecs for JSON/JSONB
    """
    global asyncpg_pool
    if asyncpg_pool is None:
        asyncpg_pool = await asyncpg.create_pool(
            dsn=database_config.POSTGRES_DATABASE_URI,
            min_size=database_config.POSTGRES_POOL_MIN_SIZE,
            max_size=database_config.POSTGRES_POOL_MAX_SIZE,
            max_queries=database_config.POSTGRES_POOL_MAX_QUERIES,
            max_inactive_connection_lifetime=database_config.POSTGRES_POOL_MAX_INACTIVE_CONNECTION_LIFETIME,
            timeout=database_config.POSTGRES_POOL_TIMEOUT,
            command_timeout=database_config.POSTGRES_POOL_COMMAND_TIMEOUT,
            init=init_connection,
        )


async def close_asyncpg_pool() -> None:
    """Closes the asyncpg connection pool gracefully during shutdown."""
    global asyncpg_pool
    if asyncpg_pool:
        await asyncpg_pool.close()
        asyncpg_pool = None


async def get_pool() -> asyncpg.Pool:
    """
    Dependency that yields the connection pool.
    Use for fan-out operations (asyncio.gather) where each task needs its own connection.
    """
    if asyncpg_pool is None:
        await init_asyncpg_pool()
    return asyncpg_pool


async def get_conn() -> AsyncGenerator[asyncpg.Connection]:
    """
    Dependency that yields a database connection from the pool.
    Use for standard sequential operations (95% of routes).
    """
    if asyncpg_pool is None:
        await init_asyncpg_pool()

    async with asyncpg_pool.acquire() as connection:
        yield connection
