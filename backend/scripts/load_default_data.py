#!/usr/bin/env python3
"""
Load default data from JSON files into the database.
File name: NNN_table_name.json (e.g. 001_users.json -> table users). Order by filename for FK safety.
Format: { "config": ["col1", "col2"], "data": [ {...}, ... ] } — config = columns used to find existing row (1 or more).
Uses sync psycopg2 (dev/init only). Run with: uv run python scripts/load_default_data.py [offline|online]
"""

import json
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json

from config.database import database_config

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_BASE = SCRIPT_DIR / "default_data"


def get_table_columns(cur, table_name: str) -> set[str]:
    cur.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = %s
           AND (is_generated = 'NEVER' OR is_generated IS NULL)""",
        (table_name,),
    )
    return {row[0] for row in cur.fetchall()}


def adapt_value(val):
    if isinstance(val, dict | list):
        return Json(val)
    return val


def load_table(cur, table_name: str, rows: list[dict], key_columns: list[str]) -> None:
    if not rows or not key_columns:
        return
    columns = get_table_columns(cur, table_name)
    missing = [c for c in key_columns if c not in columns]
    if not columns or missing:
        print(f"  ⚠️  Table {table_name} not found or key columns {missing} missing, skipping")
        return

    for row in rows:
        row_filtered = {k: v for k, v in row.items() if k in columns}
        key_values = [row_filtered.get(k) for k in key_columns]
        if any(v is None for v in key_values):
            continue

        values = [adapt_value(row_filtered[k]) for k in row_filtered]
        col_list = list(row_filtered.keys())

        where_clause = sql.SQL(" AND ").join(
            sql.SQL("{} = %s").format(sql.Identifier(k)) for k in key_columns
        )
        cur.execute(
            sql.SQL("SELECT 1 FROM {} WHERE {}").format(
                sql.Identifier(table_name),
                where_clause,
            ),
            key_values,
        )
        exists = cur.fetchone()

        if exists:
            set_cols = [c for c in col_list if c not in key_columns]
            set_values = [adapt_value(row_filtered[c]) for c in set_cols]
            set_clause = sql.SQL(", ").join(
                sql.SQL("{} = %s").format(sql.Identifier(c)) for c in set_cols
            )
            where_clause = sql.SQL(" AND ").join(
                sql.SQL("{} = %s").format(sql.Identifier(k)) for k in key_columns
            )
            cur.execute(
                sql.SQL("UPDATE {} SET {} WHERE {}").format(
                    sql.Identifier(table_name),
                    set_clause,
                    where_clause,
                ),
                set_values + key_values,
            )
            print(f"  🔄 Updated {table_name}: {dict(zip(key_columns, key_values, strict=False))}")
        else:
            placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in col_list)
            cur.execute(
                sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table_name),
                    sql.SQL(", ").join(map(sql.Identifier, col_list)),
                    placeholders,
                ),
                values,
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


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "offline"
    if mode not in ("offline", "online"):
        print("❌ Mode must be 'offline' or 'online'")
        sys.exit(1)

    data_dir = DATA_BASE / mode
    if not data_dir.exists():
        print(f"⚠️  Data directory {data_dir} not found, skipping")
        return

    print(f"📂 Loading default data from {mode}...")

    conn = psycopg2.connect(database_config.POSTGRES_DATABASE_URI)
    try:
        cur = conn.cursor()
        for json_file in sorted(data_dir.glob("*.json")):
            stem = json_file.stem
            table_name = stem.split("_", 1)[1] if "_" in stem else stem
            with open(json_file) as f:
                raw = json.load(f)
            key_columns, rows = parse_payload(raw)
            if not key_columns or not rows:
                continue
            print(f"📥 {table_name} ({len(rows)} rows, key={key_columns})")
            load_table(cur, table_name, rows, key_columns)
        conn.commit()
        cur.close()
        print("✅ Default data loaded successfully!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
