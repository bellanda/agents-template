"""Fail when a foreign key has no index that starts with its columns (audit 2026-11-13 core-performance-10).

Why: without a leading index the referenced row's DELETE/UPDATE (ON DELETE CASCADE / SET NULL
or the plain RI check) and every "rows of this parent" screen scan the whole child table. It is
invisible with small tables and becomes lock_timeout (5 s) noise at 10x data.

Rules (db/schema.sql, the dbmate snapshot, is the source of truth):

- An FK is covered when some btree index, PRIMARY KEY or UNIQUE constraint of the table has the
  FK columns, in order, as its leading columns. A partial index counts only when its predicate
  is just ``col IS NOT NULL`` (the planner proves ``col = $1`` implies it, so the RI lookup can
  use it); ``WHERE deleted_at IS NULL`` and the like cannot serve a cascade.
- Authorship FKs are exempt: a column named ``*_by`` that references ``users(id)``
  (created_by, updated_by, deleted_by...). Users are soft-deleted, so those cascades never run
  and the index would only slow every write.
- Anything else must be indexed or listed in ``ALLOWED_UNINDEXED`` below with the reason.

Run from the backend root: ``uv run python scripts/check_fk_indexes.py``. Exit 0 = clean, 1 = gaps.
``--emit-sql`` prints the CREATE INDEX statements for the gaps (used to write the migration).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "db" / "schema.sql"

# {"table.column,column": "why no index is needed"} - keep empty unless there is a real reason.
ALLOWED_UNINDEXED: dict[str, str] = {}

POSTGRES_NAME_LIMIT = 63

FK_RE = re.compile(
    r"^ALTER TABLE ONLY public\.(\w+)\s+ADD CONSTRAINT \w+ FOREIGN KEY \(([^)]*)\) "
    r"REFERENCES public\.(\w+)\(",
    re.MULTILINE,
)
KEY_RE = re.compile(
    r"^ALTER TABLE ONLY public\.(\w+)\s+ADD CONSTRAINT \w+ (?:PRIMARY KEY|UNIQUE) \(([^)]*)\)",
    re.MULTILINE,
)
INDEX_RE = re.compile(
    r"^CREATE (?:UNIQUE )?INDEX \w+ ON (?:ONLY )?public\.(\w+) USING btree "
    r"\(((?:[^()]|\([^()]*\))*)\)(?: WHERE (.*))?;$",
    re.MULTILINE,
)


def _split_columns(raw: str) -> list[str]:
    """Leading plain columns of an index definition; stops at the first expression."""
    cols: list[str] = []
    depth = 0
    current = ""
    for ch in raw + ",":
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            token = current.strip()
            current = ""
            name = re.match(r'^"?(\w+)"?(?:\s+(?:DESC|ASC|NULLS .*|\w+_ops))*$', token)
            if not name:
                break
            cols.append(name.group(1))
        else:
            current += ch
    return cols


NOT_NULL_TERM_RE = re.compile(r"^\(*(\w+) IS NOT NULL\)*$")


def _usable_for_fk(predicate: str | None) -> bool:
    if predicate is None:
        return True
    return all(NOT_NULL_TERM_RE.match(term.strip()) for term in predicate.split(" AND "))


def find_unindexed_fks(schema_text: str) -> list[tuple[str, list[str], str]]:
    """``[(table, fk_columns, referenced_table)]`` for every uncovered, non-exempt FK."""
    covers: dict[str, list[list[str]]] = {}
    for match in INDEX_RE.finditer(schema_text):
        if _usable_for_fk(match.group(3)):
            covers.setdefault(match.group(1), []).append(_split_columns(match.group(2)))
    for match in KEY_RE.finditer(schema_text):
        covers.setdefault(match.group(1), []).append(_split_columns(match.group(2)))

    gaps: list[tuple[str, list[str], str]] = []
    for match in FK_RE.finditer(schema_text):
        table, raw_cols, ref = match.group(1), match.group(2), match.group(3)
        cols = [c.strip().strip('"') for c in raw_cols.split(",")]
        if any(existing[: len(cols)] == cols for existing in covers.get(table, [])):
            continue
        if ref == "users" and len(cols) == 1 and cols[0].endswith("_by"):
            continue
        if f"{table}.{','.join(cols)}" in ALLOWED_UNINDEXED:
            continue
        gaps.append((table, cols, ref))
    return sorted(gaps)


def index_name(table: str, cols: list[str]) -> str:
    """``ix_<table>_<cols>`` (repo convention), shortened under Postgres' 63-char limit."""
    name = f"ix_{table}_{'_'.join(cols)}"
    if len(name) <= POSTGRES_NAME_LIMIT:
        return name
    keep = POSTGRES_NAME_LIMIT - 9
    digest = format(sum(ord(c) * (i + 1) for i, c in enumerate(name)) % 0xFFFFFF, "06x")
    return f"{name[:keep]}_{digest}"


def main() -> int:
    if not SCHEMA_FILE.exists():
        print(f"error: schema not found at {SCHEMA_FILE}", file=sys.stderr)
        return 2
    gaps = find_unindexed_fks(SCHEMA_FILE.read_text())
    if "--emit-sql" in sys.argv:
        for table, cols, _ref in gaps:
            print(
                f"CREATE INDEX IF NOT EXISTS {index_name(table, cols)} "
                f"ON {table}({', '.join(cols)});"
            )
        return 0
    if not gaps:
        print("✓ every foreign key has a leading index.")
        return 0
    print(f"{len(gaps)} foreign key(s) without a leading index:")
    for table, cols, ref in gaps:
        print(f"  ✗ {table}({', '.join(cols)}) -> {ref}")
    print(
        "\nAdd `CREATE INDEX IF NOT EXISTS ix_<table>_<cols> ON <table>(<cols>)` in a migration, "
        "or list the FK in ALLOWED_UNINDEXED with the reason."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
