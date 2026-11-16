"""Foreign keys keep a leading index (audit 2026-11-13 core-performance-09/10).

Two layers: unit cases for the ``scripts/check_fk_indexes.py`` rules, and a LIVE check on the
migrated test database (so a migration and ``db/schema.sql`` that drift apart are caught).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

import check_fk_indexes as fk  # noqa: E402

PARENT_FK = """
ALTER TABLE ONLY public.child
    ADD CONSTRAINT child_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.parent(id);
"""


def test_unindexed_fk_is_reported():
    assert fk.find_unindexed_fks(PARENT_FK) == [("child", ["parent_id"], "parent")]


@pytest.mark.parametrize(
    "index_sql",
    [
        "CREATE INDEX ix_a ON public.child USING btree (parent_id);",
        "CREATE INDEX ix_a ON public.child USING btree (parent_id, created_at DESC);",
        "CREATE INDEX ix_a ON public.child USING btree (parent_id) WHERE (parent_id IS NOT NULL);",
    ],
)
def test_leading_index_covers_fk(index_sql: str):
    assert fk.find_unindexed_fks(PARENT_FK + index_sql) == []


@pytest.mark.parametrize(
    "index_sql",
    [
        # fk column is not the leading one
        "CREATE INDEX ix_a ON public.child USING btree (created_at, parent_id);",
        # soft-delete partial: the RI lookup (`WHERE parent_id = $1`) cannot use it
        "CREATE INDEX ix_a ON public.child USING btree (parent_id) WHERE (deleted_at IS NULL);",
    ],
)
def test_non_serving_index_does_not_cover_fk(index_sql: str):
    assert fk.find_unindexed_fks(PARENT_FK + index_sql) == [("child", ["parent_id"], "parent")]


def test_authorship_fk_to_users_is_exempt():
    sql = """
ALTER TABLE ONLY public.child
    ADD CONSTRAINT child_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);
"""
    assert fk.find_unindexed_fks(sql) == []


def test_schema_snapshot_has_no_unindexed_fk():
    gaps = fk.find_unindexed_fks((BACKEND_ROOT / "db" / "schema.sql").read_text())
    assert gaps == [], f"foreign keys without a leading index: {gaps}"


def test_index_name_stays_within_postgres_limit():
    name = fk.index_name(
        "a_table_with_a_really_long_name_for_testing", ["some_really_long_column_id"]
    )
    assert len(name) <= fk.POSTGRES_NAME_LIMIT
    assert name == fk.index_name(
        "a_table_with_a_really_long_name_for_testing", ["some_really_long_column_id"]
    )


async def test_live_database_has_leading_index_for_every_fk(db_conn):
    rows = await db_conn.fetch(
        """
        SELECT c.conrelid::regclass::text AS tbl, array_agg(a.attname ORDER BY k.ord) AS cols
        FROM pg_constraint c
        CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
        WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace
          AND NOT (c.confrelid = 'public.users'::regclass AND cardinality(c.conkey) = 1
                   AND (SELECT attname FROM pg_attribute
                        WHERE attrelid = c.conrelid AND attnum = c.conkey[1]) LIKE '%\\_by')
          AND NOT EXISTS (
            SELECT 1 FROM pg_index i
            WHERE i.indrelid = c.conrelid AND i.indisvalid
              AND (i.indpred IS NULL
                   OR pg_get_expr(i.indpred, i.indrelid) ~ '^\\(*\\w+ IS NOT NULL\\)*$')
              AND (i.indkey::int2[])[0:cardinality(c.conkey) - 1] = c.conkey
          )
        GROUP BY c.oid, c.conrelid
        """
    )
    assert [(r["tbl"], list(r["cols"])) for r in rows] == []
