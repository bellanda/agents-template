#!/usr/bin/env python3
"""
Load default data from JSON files into the database.
File name: NNN_table_name.json (e.g. 001_users.json -> table users). Order by filename for FK safety.
Format: { "config": ["col1", "col2"], "data": [ {...}, ... ] } — config = columns used to find existing row (1 or more).
Uses asyncpg (dev/init only). Run with: uv run python scripts/load_default_data.py [offline|online]
"""

import json
import sys
from pathlib import Path

import anyio
import asyncpg

from config.database import database_config, init_connection

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_BASE = SCRIPT_DIR / "default_data"


def quote_ident(name: str) -> str:
    # Identifiers vêm de filenames locais + information_schema (trusted), nunca de
    # input externo. Quoting defensivo; valores SEMPRE parametrizados ($1, $2, ...).
    return '"' + name.replace('"', '""') + '"'


async def get_table_columns(conn: asyncpg.Connection, table_name: str) -> set[str]:
    rows = await conn.fetch(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = $1
           AND (is_generated = 'NEVER' OR is_generated IS NULL)""",
        table_name,
    )
    return {row["column_name"] for row in rows}


async def load_table(
    conn: asyncpg.Connection, table_name: str, rows: list[dict], key_columns: list[str]
) -> None:
    if not rows or not key_columns:
        return
    columns = await get_table_columns(conn, table_name)
    missing = [c for c in key_columns if c not in columns]
    if not columns or missing:
        print(f"  ⚠️  Table {table_name} not found or key columns {missing} missing, skipping")
        return

    for row in rows:
        row_filtered = {k: v for k, v in row.items() if k in columns}
        key_values = [row_filtered.get(k) for k in key_columns]
        if any(v is None for v in key_values):
            continue

        col_list = list(row_filtered.keys())
        values = [row_filtered[k] for k in col_list]

        where_clause = " AND ".join(
            f"{quote_ident(k)} = ${i}" for i, k in enumerate(key_columns, start=1)
        )
        exists = await conn.fetchval(
            f"SELECT 1 FROM {quote_ident(table_name)} WHERE {where_clause}", *key_values
        )

        if exists:
            set_cols = [c for c in col_list if c not in key_columns]
            if not set_cols:
                # Every column is part of the key — nothing to update, the
                # row's identity already matches. Skip silently.
                print(f"  ⏭️  Skipped {table_name} (no non-key columns to update)")
                continue
            set_values = [row_filtered[c] for c in set_cols]
            set_clause = ", ".join(
                f"{quote_ident(c)} = ${i}" for i, c in enumerate(set_cols, start=1)
            )
            where_clause = " AND ".join(
                f"{quote_ident(k)} = ${i}"
                for i, k in enumerate(key_columns, start=len(set_cols) + 1)
            )
            await conn.execute(
                f"UPDATE {quote_ident(table_name)} SET {set_clause} WHERE {where_clause}",
                *set_values,
                *key_values,
            )
            print(f"  🔄 Updated {table_name}: {dict(zip(key_columns, key_values, strict=False))}")
        else:
            placeholders = ", ".join(f"${i}" for i in range(1, len(col_list) + 1))
            col_idents = ", ".join(quote_ident(c) for c in col_list)
            await conn.execute(
                f"INSERT INTO {quote_ident(table_name)} ({col_idents}) VALUES ({placeholders})",
                *values,
            )
            print(f"  ✅ Inserted {table_name}: {dict(zip(key_columns, key_values, strict=False))}")


def parse_payload(raw: dict | list) -> tuple[list[str], list[dict]]:
    """Return (key_columns, rows). Supports { config, data } or legacy array."""
    if isinstance(raw, list):
        if not raw:
            return [], []
        return [next(iter(raw[0]))], raw
    if isinstance(raw, dict) and "config" in raw and "data" in raw:
        config = raw["config"]
        data = raw["data"]
        if isinstance(config, str):
            config = [config]
        return config, data if isinstance(data, list) else [data]
    return [], []


async def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "offline"
    if mode not in ("offline", "online"):
        print("❌ Mode must be 'offline' or 'online'")
        sys.exit(1)

    data_dir = DATA_BASE / mode
    if not data_dir.exists():
        print(f"⚠️  Data directory {data_dir} not found, skipping")
        return

    print(f"📂 Loading default data from {mode}...")

    conn = await asyncpg.connect(database_config.POSTGRES_DATABASE_URI, statement_cache_size=0)
    await init_connection(conn)
    try:
        async with conn.transaction():
            for json_file in sorted(data_dir.glob("*.json")):
                stem = json_file.stem
                table_name = stem.split("_", 1)[1] if "_" in stem else stem
                with open(json_file) as f:
                    raw = json.load(f)
                key_columns, rows = parse_payload(raw)
                if not key_columns or not rows:
                    continue
                print(f"📥 {table_name} ({len(rows)} rows, key={key_columns})")
                await load_table(conn, table_name, rows, key_columns)
        print("✅ Default data loaded successfully!")
    finally:
        await conn.close()


if __name__ == "__main__":
    anyio.run(main)
