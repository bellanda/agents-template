#!/usr/bin/env python3
"""
Reset and initialize PostgreSQL: drop if exists, create, apply migrations, load default data.
DANGER: Deletes all data in the database.
"""

import subprocess
from datetime import datetime
from pathlib import Path

from config import paths
from config.database import database_config

# PostgreSQL settings from config
POSTGRES_DB = database_config.POSTGRES_DB
POSTGRES_USER = database_config.POSTGRES_USER
POSTGRES_PASSWORD = database_config.POSTGRES_PASSWORD

# Commands as constants for clarity
PSQL_CMD = ["sudo", "-i", "-u", "postgres", "psql"]
PSQL_DB_CMD = ["sudo", "-i", "-u", "postgres", "psql", "-d", POSTGRES_DB]

SQL_TERMINATE_SESSIONS = (
    f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{POSTGRES_DB}' AND pid <> pg_backend_pid();"
)
SQL_DROP_DB = f'DROP DATABASE IF EXISTS "{POSTGRES_DB}";'
SQL_CREATE_OR_UPDATE_USER = f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{POSTGRES_USER}') THEN
        CREATE ROLE "{POSTGRES_USER}" LOGIN PASSWORD '{POSTGRES_PASSWORD}';
    ELSE
        ALTER ROLE "{POSTGRES_USER}" PASSWORD '{POSTGRES_PASSWORD}';
    END IF;
END
$$;
"""
SQL_CREATE_DB = (
    f'CREATE DATABASE "{POSTGRES_DB}" OWNER "{POSTGRES_USER}"; GRANT ALL PRIVILEGES ON DATABASE "{POSTGRES_DB}" TO "{POSTGRES_USER}";'
)
SQL_GRANT_SCHEMA = f'GRANT ALL ON SCHEMA public TO "{POSTGRES_USER}"; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "{POSTGRES_USER}"; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "{POSTGRES_USER}";'

BACKEND_DIR = paths.BASE_DIR


def db_exists() -> bool:
    result = subprocess.run([*PSQL_CMD, "-lqt"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return False
    databases = [line.split("|")[0].strip() for line in result.stdout.split("\n") if line.strip()]
    return POSTGRES_DB in databases


def run_psql(cmd: list[str], sql: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, input=sql, text=True, check=check, capture_output=True)


def main() -> None:
    if db_exists():
        print("💾 Creating backup...")
        backup_file = f"/tmp/{POSTGRES_DB}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        subprocess.run(
            ["sudo", "-i", "-u", "postgres", "pg_dump", "-Fc", "-f", backup_file, POSTGRES_DB],
            capture_output=True,
            check=False,
        )
        if Path(backup_file).exists():
            print(f"✅ Backup created: {backup_file}")

        print("🔌 Disconnecting sessions...")
        run_psql(PSQL_CMD, SQL_TERMINATE_SESSIONS, check=False)

        print("🗑️  Dropping existing database...")
        run_psql(PSQL_CMD, SQL_DROP_DB)

    print("👤 Creating/updating user...")
    run_psql(PSQL_CMD, SQL_CREATE_OR_UPDATE_USER)

    print("🗄️ Creating database...")
    run_psql(PSQL_CMD, SQL_CREATE_DB)

    print("🔐 Setting permissions...")
    run_psql(PSQL_DB_CMD, SQL_GRANT_SCHEMA)

    versions_dir = BACKEND_DIR / "alembic" / "versions"
    if not list(versions_dir.glob("*.py")):
        print("🚀 Generating initial migration...")
        subprocess.run(["uv", "run", "alembic", "revision", "--autogenerate", "-m", "initial"], cwd=BACKEND_DIR, check=True)

    print("🚀 Applying migrations...")
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, check=True)

    print("📥 Loading default data...")
    subprocess.run(["uv", "run", "python", "scripts/load_default_data.py", "offline"], cwd=BACKEND_DIR, check=True)

    print("✅ Database reset and initialized successfully!")


if __name__ == "__main__":
    main()
