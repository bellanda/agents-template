"""Guard: a calendar DAY is computed in the store time zone, never in the server/session one.

Timestamps are stored in UTC (TIMESTAMPTZ). "Today", per-day/month buckets, hour of day and weekday
are questions of the STORE calendar (America/Sao_Paulo, `api/core/timezone.py`). `created_at::date`,
`CURRENT_DATE`, `date_trunc('month', ts)`, `EXTRACT(hour FROM ts)`, `to_char(ts, ...)`,
`date.today()` and `datetime.now(UTC).date()` answer in the Postgres session / host zone (UTC in
the containers), which is already the NEXT day from 21:00 to 24:00 SP. Incident 2026-11-05
(emporion): dinner-peak orders counted for the next day in `/orders/stats` and the daily report,
and 6 tests failed only at night. A written rule existed since 2026-10 and did not stop it; this
scan does. What a line-based scan misses is caught by the suite itself: the test Postgres and the
pytest process run in `TEST_TIMEZONE` (UTC+14, see conftest + tests/compose.yml), where the local
date differs from São Paulo during working hours, not only at night.

Correct forms: `(col AT TIME ZONE 'America/Sao_Paulo')::date`, a half-open UTC range from
`local_day_bounds_utc(day)`, `local_today(now)` in Python, or a date computed in Python and passed
as `$n::date`.

A route `Query(...)` typed `datetime` is flagged too: the period filters send `from=2026-11-05`
(date only), Pydantic turns it into a NAIVE midnight and asyncpg reads naive as the PROCESS zone
(UTC in the containers). nexarena 2026-11-06: a custom finance period dropped its whole last day
and gained 21:00-24:00 SP of the day before its first. Take `dt.date` and build the window with
`local_day_bounds_utc`, or `pydantic.AwareDatetime` when the client sends a real instant (ISO with
an offset) so a naive value is a 422 instead of a silent shift. A flagged line that is correct (a DATE column, a value already converted, a number
formatted by `to_char`) carries `tz-ok: <why>` in a comment ON THAT LINE (`# tz-ok: …` in Python,
`-- tz-ok: …` inside SQL).

Central source, copied unedited to every app: Config Files/agents/skills/database/references/
local-time/test_timezone_guard.py.
"""

from __future__ import annotations

import ast
import datetime as dt
import io
import re
import tokenize
from collections.abc import Iterator
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCANNED_PY_DIRS = ("src", "pipelines", "cron", "scripts", "agents", "tests")
SCANNED_SQL_DIR = BACKEND_DIR / "db" / "migrations"
SKIPPED_DIR_NAMES = frozenset({".venv", "__pycache__", "node_modules", "eval_data"})
THIS_FILE = Path(__file__).resolve()
CANARY_UTC_OFFSET = dt.timedelta(hours=14)  # Pacific/Kiritimati, no DST
OK_MARKER = re.compile(r"tz-ok:\s*\S")
AT_TIME_ZONE = re.compile(r"\bat\s+time\s+zone\b|America/Sao_Paulo", re.IGNORECASE)
# `(col AT TIME ZONE $1)` and the `::date` that closes it often sit on adjacent lines.
LOOKBACK_LINES = 2

SESSION_DAY_KEYWORDS = re.compile(
    r"\b(current_date|current_time|localtimestamp|localtime)\b", re.IGNORECASE
)
# `x::date` / `x::timestamp` (no tz) — the operand is checked separately: `$1::date` and
# `'2026-01-01'::date` are values, not a conversion of a stored instant.
CAST_TO_LOCAL = re.compile(r"::\s*(date|timestamp)\b(?!\s+with\b)", re.IGNORECASE)
CAST_AS_LOCAL = re.compile(r"\bcast\s*\((.*?)\bas\s+(date|timestamp)\b(?!\s+with\b)", re.I)
CALENDAR_FUNCTIONS = re.compile(
    r"\bdate_trunc\s*\(\s*'(day|week|month|quarter|year|hour)'"
    r"|\bextract\s*\(\s*(hour|minute|dow|isodow|day|doy|week|month|quarter|year)\b"
    r"|\bdate_part\s*\(\s*'(hour|minute|dow|isodow|day|doy|week|month|quarter|year)'"
    r"|\bto_char\s*\(",
    re.IGNORECASE,
)
VALUE_OPERAND = re.compile(r"(\$\d+|'[^']*'|\$\d+\s*\)|\bnull)\s*$", re.IGNORECASE)
# Fleet naming: a stored instant (TIMESTAMPTZ) is `*_at`; DATE columns are `*_date`, `month`,
# `period_month`, `day`. A calendar operation is only flagged on a line that touches an instant,
# so `extract(day FROM period_month)` and `date_trunc('month', due_date)` stay quiet.
STORED_INSTANT = re.compile(
    r"\b\w+_at\b|\bnow\s*\(\s*\)|\b(current_timestamp|clock_timestamp|statement_timestamp"
    r"|transaction_timestamp)\b",
    re.IGNORECASE,
)

NAIVE_CLOCK_CALLS = frozenset({"today", "utcnow", "utcfromtimestamp"})
CALENDAR_ATTRS = frozenset(
    {"date", "hour", "day", "month", "year", "weekday", "isoweekday", "strftime"}
)
TIME_MODULE_LOCAL_CALLS = frozenset({"localtime", "mktime", "strftime", "ctime"})
# `datetime`, `dt.datetime`, `datetime.datetime` — not `AwareDatetime`, not `datetime.date`.
NAIVE_DATETIME_ANNOTATION = re.compile(r"(?<![\w.])(dt\.)?datetime(\.datetime)?(?![\w.])")


def iter_files(directories: tuple[str, ...], suffix: str) -> Iterator[Path]:
    for name in directories:
        root = BACKEND_DIR / name
        if not root.is_dir():
            continue
        for path in root.rglob(f"*{suffix}"):
            if path.resolve() == THIS_FILE or SKIPPED_DIR_NAMES & set(path.parts):
                continue
            yield path


def sql_violation(fragment: str, window: str) -> str | None:
    """Why this SQL fragment computes a day in the session zone, or None when it does not."""
    if SESSION_DAY_KEYWORDS.search(fragment):
        return "CURRENT_DATE/LOCALTIME* is the session-zone (UTC) day"
    if AT_TIME_ZONE.search(window) or not STORED_INSTANT.search(fragment):
        return None
    for match in CAST_TO_LOCAL.finditer(fragment):
        if not VALUE_OPERAND.search(fragment[: match.start()]):
            return "::date/::timestamp of a stored instant is the session-zone day"
    for match in CAST_AS_LOCAL.finditer(fragment):
        if not VALUE_OPERAND.search(match.group(1).strip() + " "):
            return "CAST(... AS date) of a stored instant is the session-zone day"
    if CALENDAR_FUNCTIONS.search(fragment):
        return "date_trunc/EXTRACT/to_char on a stored instant runs in the session zone"
    return None


def docstring_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        first = node.body[0] if node.body else None
        is_docstring = (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        )
        if is_docstring:
            lines.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return lines


def string_fragments_by_line(source: str, skipped: set[int]) -> dict[int, str]:
    """Text of every string literal (where SQL lives), keyed by physical line."""
    string_types = {tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", tokenize.STRING)}
    fragments: dict[int, str] = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type not in string_types:
            continue
        for offset, text in enumerate(token.string.split("\n")):
            line = token.start[0] + offset
            if line not in skipped:
                fragments[line] = fragments.get(line, "") + " " + text
    return fragments


def is_utc_argument(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "UTC"
    if isinstance(node, ast.Attribute):
        return node.attr in {"UTC", "utc"}
    return False


def python_clock_violation(node: ast.AST) -> str | None:
    """Why this call reads the host/UTC calendar, or None."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        name, owner = node.func.attr, node.func.value
        owner_name = owner.id if isinstance(owner, ast.Name) else getattr(owner, "attr", "")
        if name in NAIVE_CLOCK_CALLS and owner_name in {"date", "datetime"}:
            return f"{owner_name}.{name}() is the host-zone clock; use local_today()/now(UTC)"
        if name == "now" and owner_name == "datetime" and not node.args and not node.keywords:
            return "datetime.now() without tz is the host-zone clock"
        if name == "fromtimestamp" and len(node.args) < 2 and not node.keywords:
            return "fromtimestamp() without tz is the host-zone clock"
        if name in TIME_MODULE_LOCAL_CALLS and owner_name == "time":
            return f"time.{name}() is the host-zone calendar"
    if isinstance(node, ast.Attribute) and node.attr in CALENDAR_ATTRS:
        call = node.value
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "now"
            and call.args
            and is_utc_argument(call.args[0])
        ):
            return f"now(UTC).{node.attr} is the UTC calendar; convert with store_tz first"
    return None


def is_query_call(node: ast.expr | None) -> bool:
    if not isinstance(node, ast.Call):
        return False
    return getattr(node.func, "id", getattr(node.func, "attr", "")) == "Query"


def naive_datetime_query_params(tree: ast.AST) -> list[tuple[int, str]]:
    """Route parameters `x: datetime = Query(...)` (or `Annotated[datetime, Query()]`)."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        positional = node.args.posonlyargs + node.args.args
        defaulted = positional[len(positional) - len(node.args.defaults) :]
        pairs = list(zip(defaulted, node.args.defaults, strict=True))
        pairs += list(zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True))
        for arg, default in pairs:
            annotation = ast.unparse(arg.annotation) if arg.annotation else ""
            is_query = is_query_call(default) or "Query(" in annotation
            if is_query and NAIVE_DATETIME_ANNOTATION.search(annotation):
                found.append(
                    (
                        arg.lineno,
                        "naive datetime Query param: a date-only value becomes UTC midnight; "
                        "take dt.date + local_day_bounds_utc, or AwareDatetime",
                    )
                )
    return found


def statement_lines(tree: ast.AST, line: int) -> range:
    """Lines of the innermost simple statement containing `line`. `ruff format` splits a long call
    and moves the trailing `# tz-ok:` to the closing line (kailos check.sh, 2026-11-06), so a
    Python-call finding accepts the marker anywhere in its statement. SQL stays line-strict: one
    marker must not exempt a whole query."""
    spans = [
        (node.lineno, node.end_lineno or node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.stmt) and not hasattr(node, "body")
    ]
    containing = [span for span in spans if span[0] <= line <= span[1]]
    if not containing:
        return range(line, line + 1)
    start, end = min(containing, key=lambda span: span[1] - span[0])
    return range(start, end + 1)


def python_call_findings(tree: ast.AST) -> list[tuple[int, str]]:
    found = [
        (node.lineno, reason) for node in ast.walk(tree) if (reason := python_clock_violation(node))
    ]
    return found + naive_datetime_query_params(tree)


def python_violations(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    raw_lines = source.splitlines()
    tree = ast.parse(source)
    fragments = string_fragments_by_line(source, docstring_lines(tree))
    found: list[tuple[int, str, range]] = []
    for line, fragment in fragments.items():
        window = " ".join(fragments.get(n, "") for n in range(line - LOOKBACK_LINES, line + 1))
        reason = sql_violation(fragment, window)
        if reason:
            found.append((line, reason, range(line, line + 1)))
    for line, reason in python_call_findings(tree):
        found.append((line, reason, statement_lines(tree, line)))
    return [
        f"{path.relative_to(BACKEND_DIR)}:{line}: {reason}\n    {raw_lines[line - 1].strip()}"
        for line, reason, marker_lines in sorted(set(found), key=lambda item: item[:2])
        if not any(OK_MARKER.search(raw_lines[n - 1]) for n in marker_lines)
    ]


def sql_file_violations(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    code = [line.split("--", 1)[0] for line in lines]
    found: list[str] = []
    for index, fragment in enumerate(code):
        window = " ".join(code[max(0, index - LOOKBACK_LINES) : index + 1])
        reason = sql_violation(fragment, window)
        if reason and not OK_MARKER.search(lines[index]):
            found.append(
                f"{path.relative_to(BACKEND_DIR)}:{index + 1}: {reason}\n    {lines[index].strip()}"
            )
    return found


async def test_suite_runs_in_the_calendar_canary_zone(db_conn):
    """Without the canary the night-only bugs hide again: both clocks must be in TEST_TIMEZONE."""
    from tests.conftest import TEST_TIMEZONE

    assert await db_conn.fetchval("SHOW timezone") == TEST_TIMEZONE
    assert dt.datetime.now().astimezone().utcoffset() == CANARY_UTC_OFFSET


def test_days_are_computed_in_the_store_time_zone():
    violations = [v for path in iter_files(SCANNED_PY_DIRS, ".py") for v in python_violations(path)]
    if SCANNED_SQL_DIR.is_dir():
        violations += [
            v for path in SCANNED_SQL_DIR.glob("*.sql") for v in sql_file_violations(path)
        ]
    assert not violations, (
        "Day computed in the server/session time zone (wrong from 21:00 to 24:00 SP). Use "
        "`AT TIME ZONE` / local_day_bounds_utc / local_today, or mark a correct line with "
        "`tz-ok: <why>`:\n" + "\n".join(violations)
    )
