"""Restore rehearsal of config/backup/pg_backup.sh (`rehearse-dump FILE`), audit infra-live-16.

A dump that was never restored is not a backup: the monthly rehearsal restores it into the scratch
database `<db>_rehearsal`, checks tables and migrations came back, and always drops the scratch
database. Runs against the pytest Postgres container with the host's pg tools.
"""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = next(
    parent / "config/backup/pg_backup.sh"
    for parent in Path(__file__).resolve().parents
    if (parent / "config/backup/pg_backup.sh").exists()
)
# The pytest Postgres port differs per repo (5433/5434/5436/5441): read this repo's default from
# tests/compose.yml instead of hardcoding one (a literal 5433 errored at setup in every repo on
# another port whenever TEST_DB_PORT was unset, i.e. under check.sh; found 2026-11-16).
DEFAULT_TEST_DB_PORT = re.search(
    r"TEST_DB_PORT:-(\d+)", (Path(__file__).resolve().parents[1] / "compose.yml").read_text()
).group(1)
# One source database per xdist worker: the two tests of this file can land on different workers
# and each fixture drops/creates the database (a shared name made CREATE DATABASE collide).
SOURCE_DB = f"rehearsal_source_{os.environ.get('PYTEST_XDIST_WORKER', 'main')}"
SCRATCH_DB = f"{SOURCE_DB}_rehearsal"
PG_ENV = {
    **os.environ,
    "PGHOST": "localhost",
    "PGPORT": os.environ.get("TEST_DB_PORT", DEFAULT_TEST_DB_PORT),
    "PGUSER": "postgres",
    "PGPASSWORD": "postgres",
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": "postgres",
    "POSTGRES_DB": SOURCE_DB,
    "BACKUP_APP": "testapp",
}


def psql(database: str, sql: str) -> str:
    command = ["psql", "-X", "-At", "-v", "ON_ERROR_STOP=1", "-d", database, "-c", sql]
    return subprocess.run(
        command, env=PG_ENV, capture_output=True, text=True, check=True
    ).stdout.strip()


def scratch_database_exists() -> bool:
    return (
        psql("postgres", f"SELECT count(*) FROM pg_database WHERE datname = '{SCRATCH_DB}'") == "1"
    )


@pytest.fixture
def dump_file(tmp_path: Path):
    psql("postgres", f'DROP DATABASE IF EXISTS "{SOURCE_DB}" WITH (FORCE)')
    psql("postgres", f'CREATE DATABASE "{SOURCE_DB}"')
    psql(SOURCE_DB, "CREATE TABLE schema_migrations (version text PRIMARY KEY)")
    psql(SOURCE_DB, "INSERT INTO schema_migrations VALUES ('20260101000000')")
    psql(SOURCE_DB, "CREATE TABLE customers (id int PRIMARY KEY, name text)")
    path = tmp_path / "testapp.dump"
    subprocess.run(["pg_dump", "-Fc", "-d", SOURCE_DB, "-f", str(path)], env=PG_ENV, check=True)
    yield path
    psql("postgres", f'DROP DATABASE IF EXISTS "{SOURCE_DB}" WITH (FORCE)')


def rehearse(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), "rehearse-dump", str(path)],
        env=PG_ENV,
        capture_output=True,
        text=True,
        check=False,
    )


def test_rehearsal_restores_the_dump_reports_what_came_back_and_drops_the_scratch_database(
    dump_file: Path,
) -> None:
    completed = rehearse(dump_file)

    assert completed.returncode == 0, completed.stderr
    step = json.loads(completed.stdout.strip().splitlines()[-1])
    assert (step["event"], step["status"]) == ("rehearsal", "ok")
    assert step["message"] == "tables=2 live_tables=2 migrations=1"
    assert not scratch_database_exists()


def test_rehearsal_fails_on_a_dump_that_cannot_be_restored_and_still_cleans_up(
    dump_file: Path,
) -> None:
    dump_file.write_bytes(
        dump_file.read_bytes()[: dump_file.stat().st_size // 2]
    )  # truncated upload

    completed = rehearse(dump_file)

    assert completed.returncode != 0
    assert '"rehearsal"' not in completed.stdout
    assert not scratch_database_exists()
