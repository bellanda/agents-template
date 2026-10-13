"""Pytest bootstrap: hermetic settings + parallel-safe Postgres fixtures (`db_engine`, `db_conn`).

Settings load at import time (config/settings.py), so the hermetic test yaml and the required
secrets must be in env BEFORE any `api.*` import. Without this, collecting any test that imports
the app fails with "DATABASE_URL is not set at .env" (2026-10-13).

xdist (2026-10-13, canonical impl: kailos `backend/tests/conftest.py`): the controller migrates
ONCE into the template DB (see `pytest_configure`), then every worker clones it into its own
`{base}_<gwN>` database with CREATE DATABASE ... TEMPLATE (file copy, <1s). Workers share only
the Postgres server. `TEST_DB_PORT` moves the suite to another Postgres port (compose maps the
same var). Tests that need an extra committed connection must use `TEST_DATABASE_DSN`.
"""

import os
import subprocess
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = _TESTS_DIR.parent
os.environ["APP_YAML_PATH"] = str(_TESTS_DIR / "app.test.yaml")

_DEFAULT_PG_PORT = "5441"  # keep in sync with tests/compose.yml; fleet apps use 5433/5434/5436
_BASE_DB_NAME = "test_agents_template"
_TEMPLATE_DB_NAME = "test_agents_template_template"
# Set by xdist in every worker's environment before conftest import ("gw0", "gw1", ...);
# absent in a plain `pytest` run and in the xdist controller -> serial path unchanged.
_XDIST_WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER")

_TEST_DB_PORT = os.environ.get("TEST_DB_PORT", _DEFAULT_PG_PORT)
_TEST_DB_NAME = _BASE_DB_NAME if _XDIST_WORKER_ID is None else f"{_BASE_DB_NAME}_{_XDIST_WORKER_ID}"
_TEST_DATABASE_URL_TEMPLATE = "postgres://postgres:postgres@localhost:{port}/{db}?sslmode=disable"
# dbmate reads this to bootstrap the test schema (sslmode=disable: local pg without TLS).
os.environ["TEST_DATABASE_URL"] = _TEST_DATABASE_URL_TEMPLATE.format(
    port=_TEST_DB_PORT, db=_TEST_DB_NAME
)
# `config.database` fails fast on import without DATABASE_URL. Workers inherit the controller's
# env (already pointing at the base DB), so they must override it.
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

import asyncpg  # noqa: E402
import pytest  # noqa: E402

from config.database import init_connection  # noqa: E402

_ADMIN_DSN = f"postgresql://postgres:postgres@localhost:{_TEST_DB_PORT}/postgres"
# Public: tests that open extra committed connections import this to follow the worker's DB.
TEST_DATABASE_DSN = f"postgresql://postgres:postgres@localhost:{_TEST_DB_PORT}/{_TEST_DB_NAME}"


def _dbmate(database_url_env: str, *args: str, check: bool = True) -> None:
    result = subprocess.run(
        ["dbmate", "-e", database_url_env, *args],
        cwd=BACKEND_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"dbmate {' '.join(args)} failed: {result.stderr or result.stdout}")


def _is_xdist_controller(config: pytest.Config) -> bool:
    """True only in the xdist master process of a run that actually distributes."""
    if hasattr(config, "workerinput"):
        return False
    return bool(getattr(config.option, "numprocesses", None))


def pytest_configure(config: pytest.Config) -> None:
    """xdist controller: migrate the schema once into the template database.

    Workers never run dbmate; they clone this template (see `db_engine`). Runs before the
    workers are spawned.
    """
    if not _is_xdist_controller(config):
        return
    os.environ["TEMPLATE_DATABASE_URL"] = _TEST_DATABASE_URL_TEMPLATE.format(
        port=_TEST_DB_PORT, db=_TEMPLATE_DB_NAME
    )
    _dbmate("TEMPLATE_DATABASE_URL", "drop", check=False)
    _dbmate("TEMPLATE_DATABASE_URL", "--no-dump-schema", "up")
    config._template_db_ready = True


def pytest_unconfigure(config: pytest.Config) -> None:
    if getattr(config, "_template_db_ready", False):
        _dbmate("TEMPLATE_DATABASE_URL", "drop", check=False)


async def _admin_execute(statement: str) -> None:
    admin = await asyncpg.connect(dsn=_ADMIN_DSN)
    try:
        await admin.execute(statement)
    finally:
        await admin.close()


_SHARED_CONN: dict[str, asyncpg.Connection] = {}


async def _shared_test_connection() -> asyncpg.Connection:
    """One connection per test PROCESS; the per-test transaction is the isolation boundary.

    Opening a fresh connection per test costs ~18ms (SCRAM + backend fork) — over half of a
    large suite's wall time (kailos). Reopens if a test closed/killed the connection.
    """
    conn = _SHARED_CONN.get("conn")
    if conn is None or conn.is_closed():
        conn = await asyncpg.connect(dsn=TEST_DATABASE_DSN)
        await init_connection(conn)
        _SHARED_CONN["conn"] = conn
    return conn


async def _close_shared_test_connection() -> None:
    conn = _SHARED_CONN.pop("conn", None)
    if conn is not None and not conn.is_closed():
        await conn.close()


@pytest.fixture(scope="session")
async def db_engine():
    """Test schema bootstrap, once per session (serial) or per worker (xdist).

    Serial: dbmate drop + up on the base DB. xdist: the controller already migrated the
    template; the worker only clones it and drops the clone at the end.
    """
    if _XDIST_WORKER_ID is not None:
        await _admin_execute(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}" WITH (FORCE)')
        await _admin_execute(f'CREATE DATABASE "{_TEST_DB_NAME}" TEMPLATE "{_TEMPLATE_DB_NAME}"')
        yield None
        await _close_shared_test_connection()
        await _admin_execute(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}" WITH (FORCE)')
        return
    _dbmate("TEST_DATABASE_URL", "drop", check=False)
    _dbmate("TEST_DATABASE_URL", "--no-dump-schema", "up")
    yield None
    # No `drop` here: the shared connection is still open and Postgres would wait ~5s for it;
    # the next session's initial `drop` already returns a clean DB.
    await _close_shared_test_connection()


@pytest.fixture
async def db_conn(db_engine):
    """Shared connection inside a transaction that is always rolled back."""
    conn = await _shared_test_connection()
    tr = conn.transaction()
    await tr.start()
    try:
        yield conn
    finally:
        await tr.rollback()
        # Same as a pool release: clears GUCs (`SET`), LISTEN, advisory locks and cursors
        # a test left behind. A connection the test broke is replaced on the next test.
        await conn.reset()


def pytest_make_parametrize_id(config, val, argname):
    """Stable test ids for generated bytes (PDF /ID, zip timestamps differ per process).

    pytest-xdist requires every worker to collect the identical test list; a bytes-derived id
    changes per worker and aborts the run with "Different tests were collected" (2026-10-13).
    Duplicate ids get pytest's own index suffix.
    """
    if isinstance(val, bytes | bytearray):
        return f"{argname}-bytes"
    return None
