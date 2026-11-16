"""Template runtime-infra guards (audit 2026-11-13: infra-live-04/06, core-performance-04)."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def test_preloaded_pg_stat_statements_has_its_extension_migration() -> None:
    assert "pg_stat_statements" in (REPO / "compose.yaml").read_text()
    migrations = (REPO / "backend/db/migrations").glob("*.sql")
    assert any(
        "CREATE EXTENSION IF NOT EXISTS pg_stat_statements" in p.read_text() for p in migrations
    )
    assert "pg_stat_statements" in (REPO / "backend/db/schema.sql").read_text()


def test_backend_healthcheck_is_http_not_a_bare_socket() -> None:
    compose = (REPO / "compose.yaml").read_text()
    assert "urllib.request.urlopen" in compose and "s.connect(" not in compose


def test_no_consumer_polls_nats_with_a_short_fixed_timeout() -> None:
    offenders = [
        str(path.relative_to(REPO))
        for path in (REPO / "backend/src").rglob("*.py")
        if path.name != "consumer_support.py"
        and (
            re.search(r"\bsub\.fetch\(", path.read_text())
            or re.search(r"^FETCH_TIMEOUT_SECONDS\b.*=\s*[0-9.]+\s*$", path.read_text(), re.M)
        )
    ]
    assert not offenders, offenders
