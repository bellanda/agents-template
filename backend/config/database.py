"""PostgreSQL connection layer for the API.

- DSN single source of truth: `settings.database_url` (`.env > DATABASE_URL` on the host,
  compose `environment:` in docker). It carries the password, so it is a secret.
- Pool kwargs (asyncpg) come from `settings.postgres.pool` (yaml).
- Schema is managed by dbmate (`backend/db/migrations/`); never created at startup.
- orjson codec installed on every connection for fast json/jsonb.
"""

from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import asyncpg
import orjson

from config.settings import settings

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
    Initializes the asyncpg connection pool from `settings.postgres.pool` + `settings.database_url`.

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
        pool_cfg = settings.postgres.pool
        asyncpg_pool = await asyncpg.create_pool(
            dsn=settings.database_url.get_secret_value(),
            min_size=pool_cfg.min_size,
            max_size=pool_cfg.max_size,
            max_queries=pool_cfg.max_queries,
            max_inactive_connection_lifetime=pool_cfg.max_inactive_connection_lifetime,
            timeout=pool_cfg.timeout,
            command_timeout=pool_cfg.command_timeout,
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


# ----------------------------------------------------------------------------
# CONNECTION SCOPE: work that alternates DB and slow network (LLM, SSE)
# ----------------------------------------------------------------------------

# One DB phase: `async with scope() as db:`.
ConnScope = Callable[[], AbstractAsyncContextManager[asyncpg.Connection]]


@asynccontextmanager
async def _reuse(conn: asyncpg.Connection) -> AsyncIterator[asyncpg.Connection]:
    yield conn


@asynccontextmanager
async def _from_pool() -> AsyncIterator[asyncpg.Connection]:
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection


def db_scope(conn: asyncpg.Connection | None) -> ConnScope:
    """Connection provider for code that alternates DB and a slow external call.

    With `conn` (test inside a transaction) every phase runs on THAT connection, which keeps
    the test's rollback boundary. Without it each phase takes a connection from the pool and
    returns it before the slow part. Audit 2026-11-13 core-performance-01: `Depends(get_conn)`
    is a yield-dependency, so FastAPI only returns the connection AFTER the whole
    StreamingResponse is sent; a chat stream that lives for minutes then pins 1 of `max_size`
    connections per answer and the pool starves.
    """
    if conn is not None:
        return lambda: _reuse(conn)
    return _from_pool


def get_conn_scope() -> ConnScope:
    """`Depends` for routes that call an LLM / stream: each DB phase borrows and returns a
    connection instead of `get_conn` holding one for the whole response. Tests override this
    dependency with `db_scope(db_conn)`. Rule: a route that returns a `StreamingResponse`
    never receives `conn: Connection = Depends(get_conn)`."""
    return db_scope(None)
