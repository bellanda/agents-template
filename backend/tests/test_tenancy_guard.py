"""Guard: every backend SQL statement on a tenant table carries an organization predicate.

Tenant table = any table of `db/schema.sql` with an `organization_id` column. A statement in ANY
backend module (repositories, services, routes, consumers, agents, cron, pipelines, scripts; widened
on 2026-11-14: SQL written outside `*_repository.py` was a blind spot, e.g. a rotation helper and a
dispatcher that queried queues by id alone) that reads, updates or deletes one of them must filter by `organization_id` (directly,
through a dynamic WHERE fragment built in the same function, or through a join/equality to a row of
the same statement that is already scoped). A lookup by primary key alone (`WHERE id = $1`) is the
classic cross-tenant hole (IDOR): it works in every test with one organization and leaks the row of
another store in production. Written by user request on 2026-11-13 ("the agent keeps forgetting
multi-tenant in some places"): the written rule existed and did not stop it; this scan does.

A flagged statement that is correct carries `tenant-ok: <why>` (a real reason: who already scoped
the id, why the table is global) in a comment ON the statement (`# tenant-ok: ...` in Python,
`-- tenant-ok: ...` inside the SQL), on the line right above it, or on the `def` line / the line
above the `def` of the enclosing function to cover every statement of that function.

Child tables (added 2026-11-14): a table WITHOUT `organization_id` that has a foreign key, directly
or through another child, to a tenant table (e.g. `service_order_items` -> `service_orders`) is
invisible to the check above, yet `UPDATE service_order_items ... WHERE id = $1` is the same IDOR.
A statement that references a child table passes only if the same statement mentions
`organization_id` as a PREDICATE (not merely listed in a SELECT list / RETURNING; a JOIN or EXISTS on the tenant ancestor, or a dynamic WHERE fragment of
the same function) or carries `tenant-ok: <why>`. Tables with no FK path to a tenant table (users,
reference/lookup tables) stay out.

What is NOT checked (by design): plain `INSERT ... VALUES` (the row carries its own organization_id;
the column is NOT NULL in the schema), `ON CONFLICT` targets,
tables whose tenant column has another name (e.g. `organizer_organization_id`).

Central source, copied unedited to every app: Config Files/agents/skills/database/references/
tenancy/test_tenancy_guard.py.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = BACKEND_DIR / "db" / "schema.sql"
SCANNED_DIRS = ("src", "pipelines", "cron", "agents", "scripts")
SKIPPED_DIR_NAMES = frozenset({".venv", "__pycache__", "node_modules", "tests"})
TENANT_COLUMN = "organization_id"
OK_MARKER = re.compile(r"tenant-ok:\s*\S")

SQL_START = re.compile(r"^\s*(?:--[^\n]*\n\s*)*(select|update|delete|with|insert)\b", re.IGNORECASE)
TABLE_REF = re.compile(
    r"\b(?:from|join|update|using)\s+(?:only\s+)?(?:\"?\w+\"?\.)?\"?(\w+)\"?"
    r"(?:\s+(?:as\s+)?(\w+))?",
    re.IGNORECASE,
)
CTE_NAME = re.compile(
    r"(?:\bwith(?:\s+recursive)?|,)\s*(\w+)\s+as\s*(?:not\s+)?(?:materialized\s*)?\(", re.I
)
NOT_AN_ALIAS = frozenset(
    {
        "where", "on", "set", "left", "right", "inner", "outer", "cross", "full", "join", "using",
        "group", "order", "limit", "offset", "returning", "for", "union", "except", "intersect",
        "natural", "lateral", "select", "values", "as", "and", "or", "from", "having", "window",
    }
)  # fmt: skip
# A column LISTED in `SELECT ... FROM` or `RETURNING ...` is not a predicate: `SELECT {_COLUMNS}
# FROM t WHERE id = $1` with `organization_id` inside _COLUMNS used to count as scoped (gap found
# 2026-11-14 on whatsapp_conversations get_by_id). Predicates are looked up with these removed.
SELECT_LIST = re.compile(r"\bselect\b.*?\bfrom\b", re.I | re.S)
RETURNING_LIST = re.compile(r"\breturning\b[^)]*", re.I)
EQUALITY = re.compile(r"\b(\w+)\.(\w+)(?:::\w+)?\s*=\s*(\w+)\.(\w+)\b")
PLACEHOLDER = "\x00"  # an f-string `{expr}` we could not resolve to a constant


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    function: str
    tables: tuple[str, ...]

    def __str__(self) -> str:
        return f"{self.path}:{self.line} {self.function}() reads/writes {', '.join(self.tables)} without organization_id"


FOREIGN_KEY = re.compile(
    r"ALTER TABLE ONLY (?:\"?\w+\"?\.)?\"?(\w+)\"?\s+ADD CONSTRAINT \S+ FOREIGN KEY \(([^)]*)\) "
    r"REFERENCES (?:\"?\w+\"?\.)?\"?(\w+)\"?",
    re.I,
)


def child_tables_from_schema(schema_sql: str) -> frozenset[str]:
    """Tables without `organization_id` that reach a tenant table through foreign keys.

    Transitive: a table referencing a child is a child too. Tables whose only FKs point at global
    tables (users, lookups) or at `organizations` itself (not a tenant table: it has no
    `organization_id` column) are not children; the root itself is excluded too.
    """
    tenant = tenant_tables_from_schema(schema_sql)
    parents: dict[str, set[str]] = {}
    roots: set[str] = set()  # the tenant root (`organizations`): target of organization_id FKs
    for table, columns, target in FOREIGN_KEY.findall(schema_sql):
        if columns.strip() == TENANT_COLUMN:
            roots.add(target)
        parents.setdefault(table, set()).add(target)
    children: set[str] = set()
    grown = True
    while grown:
        grown = False
        for table, targets in parents.items():
            if table in tenant or table in children or table in roots:
                continue
            if targets & (tenant | children):
                children.add(table)
                grown = True
    return frozenset(children)


def tenant_tables_from_schema(schema_sql: str) -> frozenset[str]:
    """Tables that declare an `organization_id` column in a pg_dump style schema.sql."""
    tables: set[str] = set()
    for match in re.finditer(
        r"CREATE TABLE (?:\"?\w+\"?\.)?\"?(\w+)\"? \((.*?)\n\);", schema_sql, re.S
    ):
        columns = re.findall(r"^\s+\"?(\w+)\"?\s", match.group(2), re.M)
        if TENANT_COLUMN in columns:
            tables.add(match.group(1))
    return frozenset(tables)


# ----------------------------------------------------------------------------- SQL text rendering


def module_constants(tree: ast.Module) -> dict[str, ast.expr]:
    found: dict[str, ast.expr] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            found[node.targets[0].id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            found[node.target.id] = node.value
    return found


def render(node: ast.expr, names: dict[str, ast.expr], depth: int = 0) -> str | None:
    """Best-effort text of a string expression; unresolved `{expr}` becomes PLACEHOLDER."""
    if depth > 6:
        return PLACEHOLDER
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                parts.append(render(value.value, names, depth + 1) or PLACEHOLDER)
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = render(node.left, names, depth + 1), render(node.right, names, depth + 1)
        if left is None and right is None:
            return None
        return (left or PLACEHOLDER) + (right or PLACEHOLDER)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return render(node.left, names, depth + 1)
    if isinstance(node, ast.Name) and node.id in names:
        return render(names[node.id], names, depth + 1)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"format", "strip", "lstrip", "rstrip"}
    ):
        return render(node.func.value, names, depth + 1)
    return None


def enclosing_functions(tree: ast.Module) -> dict[int, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Map id(node) -> innermost enclosing function for every node."""
    owner: dict[int, ast.FunctionDef | ast.AsyncFunctionDef] = {}

    def visit(node: ast.AST, current: ast.FunctionDef | ast.AsyncFunctionDef | None) -> None:
        for child in ast.iter_child_nodes(node):
            nxt = child if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) else current
            if nxt is not None:
                owner[id(child)] = nxt
            visit(child, nxt)

    visit(tree, None)
    return owner


@dataclass
class Statement:
    node: ast.expr
    text: str
    function: ast.FunctionDef | ast.AsyncFunctionDef | None


def without_parentheses(sql: str) -> str:
    """SQL with every (nested) parenthesised group blanked: a WHERE inside a sub-select of the
    select list does not make the statement a complete one."""
    previous = None
    while previous != sql:
        previous, sql = sql, re.sub(r"\([^()]*\)", " ", sql)
    return sql


def interpolated_names(tree: ast.Module) -> set[str]:
    """Names used inside an f-string / `+` concatenation: a module constant that is only a SQL
    FRAGMENT (e.g. `_SELECT = "SELECT ... FROM t JOIN ..."`, the WHERE appended by each caller)
    is judged where it is completed, because the rendering above resolves the constant there."""
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FormattedValue | ast.BinOp):
            used.update(n.id for n in ast.walk(node) if isinstance(n, ast.Name))
    return used


def iter_statements(tree: ast.Module) -> Iterator[Statement]:
    """Outermost string expressions that render to SQL (nested pieces are not repeated)."""
    constants = module_constants(tree)
    owner = enclosing_functions(tree)
    skipped: set[int] = set()
    fragments = {
        id(value)
        for name, value in constants.items()
        if name in interpolated_names(tree)
        and (rendered := render(value, constants)) is not None
        and not re.search(r"\bwhere\b", without_parentheses(rendered), re.I)
    }
    for node in ast.walk(tree):
        if (
            id(node) in skipped
            or id(node) in fragments
            or not isinstance(node, ast.Constant | ast.JoinedStr | ast.BinOp | ast.Call)
        ):
            continue
        function = owner.get(id(node))
        names = dict(constants)
        if function is not None:  # function-local `sql = "..."` constants
            for inner in ast.walk(function):
                if (
                    isinstance(inner, ast.Assign)
                    and len(inner.targets) == 1
                    and isinstance(inner.targets[0], ast.Name)
                    and isinstance(inner.value, ast.Constant | ast.JoinedStr | ast.BinOp)
                ):
                    names[inner.targets[0].id] = inner.value
        text = render(node, names)
        if text is None or not SQL_START.match(text):
            continue
        skipped.update(id(child) for child in ast.walk(node) if child is not node)
        yield Statement(node, text, function)


# ----------------------------------------------------------------------------- scoping analysis


def referenced_tables(sql: str, tenant: frozenset[str]) -> tuple[list[tuple[str, str]], set[str]]:
    """([(tenant_table, alias)], cte_names) found in the statement (INSERT targets excluded)."""
    ctes = {name.lower() for name in CTE_NAME.findall(sql)}
    found: list[tuple[str, str]] = []
    for match in TABLE_REF.finditer(sql):
        table = match.group(1)
        if table.lower() in ctes or table not in tenant:
            continue
        alias = match.group(2)
        found.append((table, alias if alias and alias.lower() not in NOT_AN_ALIAS else table))
    return found, ctes


def predicate_text(sql: str) -> str:
    """The statement without its SELECT list and RETURNING list (columns listed there are not
    predicates)."""
    return RETURNING_LIST.sub(" ", SELECT_LIST.sub(" select from ", sql))


def unscoped_children(sql: str, children: frozenset[str], sibling_scope: bool) -> list[str]:
    """Child tables of the statement when it has no `organization_id` predicate at all (a JOIN or
    EXISTS on the tenant ancestor, or a dynamic WHERE fragment of the same function)."""
    if not children or sibling_scope:
        return []
    if re.search(rf"\b{TENANT_COLUMN}\b", predicate_text(sql)):
        return []
    refs, _ = referenced_tables(sql, children)
    return sorted({table for table, _ in refs})


def unscoped_tables(sql: str, tenant: frozenset[str], sibling_scope: bool) -> list[str]:
    """Tenant tables of the statement with no organization_id predicate and no scoped join."""
    refs, ctes = referenced_tables(sql, tenant)
    if not refs:
        return []
    predicates = predicate_text(sql)
    bare = re.search(rf"(?<![\w.]){TENANT_COLUMN}\b", predicates) is not None
    only_one = len({table for table, _ in refs}) == 1  # bare column is unambiguous then
    scoped: set[str] = set()
    for table, alias in refs:
        qualified = re.search(
            rf"\b(?:{re.escape(alias)}|{re.escape(table)})\.{TENANT_COLUMN}\b", predicates
        )
        if qualified or (bare and only_one) or (sibling_scope and only_one):
            scoped.add(alias)
    # An equality between a scoped alias and any other alias scopes the other one too (a join to
    # a row of the same statement that is already scoped; a correlated subquery; a CTE of a scoped
    # statement). Aliases of non-tenant tables propagate it, so chains like
    # v.organization_id = $1 -> vp.vehicle_id = v.id -> uf.id = vp.file_id are followed.
    scoped_names = {alias.lower() for alias in scoped}
    edges = [(a.lower(), c.lower()) for a, _, c, _ in EQUALITY.findall(predicates)]
    grown = True
    while grown:
        grown = False
        for left, right in edges:
            for here, there in ((left, right), (right, left)):
                reached = here in scoped_names or (
                    here in ctes and (scoped_names or bare or sibling_scope)
                )
                if reached and there not in scoped_names:
                    scoped_names.add(there)
                    grown = True
    return sorted({table for table, alias in refs if alias.lower() not in scoped_names})


def sibling_has_scope(function: ast.AST | None, statements: set[int]) -> bool:
    """A dynamic WHERE fragment of the same function (`"organization_id = $1"`) scopes `{where}`."""
    if function is None:
        return False
    for node in ast.walk(function):
        if (
            id(node) in statements
            or not isinstance(node, ast.Constant)
            or not isinstance(node.value, str)
        ):
            continue
        if TENANT_COLUMN in node.value and re.search(r"[=$]|\bany\b|\bin\b", node.value, re.I):
            return True
    return False


def marker_lines(source_lines: list[str], statement: Statement) -> list[str]:
    start = statement.node.lineno
    end = statement.node.end_lineno or start
    lines = source_lines[max(start - 2, 0) : end]
    function = statement.function
    if function is not None:
        first = min([function.lineno, *(d.lineno for d in function.decorator_list)])
        body_start = function.body[0].lineno
        lines += source_lines[max(first - 2, 0) : max(body_start - 1, first)]
    return lines


def scan_source(
    source: str, rel_path: str, tenant: frozenset[str], children: frozenset[str] = frozenset()
) -> list[Violation]:
    tree = ast.parse(source)
    lines = source.splitlines()
    statements = list(iter_statements(tree))
    statement_ids = {id(item.node) for item in statements}
    violations: list[Violation] = []
    for item in statements:
        if re.match(r"\s*insert\b", item.text, re.I) and not re.search(
            r"\bselect\b", item.text, re.I
        ):
            continue
        sibling = sibling_has_scope(item.function, statement_ids)
        missing = unscoped_tables(item.text, tenant, sibling) + unscoped_children(
            item.text, children, sibling
        )
        if not missing:
            continue
        if any(OK_MARKER.search(line) for line in marker_lines(lines, item)):
            continue
        name = item.function.name if item.function is not None else "<module>"
        violations.append(Violation(rel_path, item.node.lineno, name, tuple(missing)))
    return violations


def backend_files() -> Iterator[Path]:
    for name in SCANNED_DIRS:
        root = BACKEND_DIR / name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if not SKIPPED_DIR_NAMES & set(path.parts):
                yield path


# ----------------------------------------------------------------------------- tests

SYNTHETIC_TENANT = frozenset({"vehicles", "visits"})


def synthetic(sql_body: str) -> list[Violation]:
    source = f"async def load(conn, org, vid):\n{sql_body}\n"
    return scan_source(source, "x_repository.py", SYNTHETIC_TENANT)


def test_backend_sql_scopes_every_tenant_table_by_organization() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    tenant = tenant_tables_from_schema(schema)
    children = child_tables_from_schema(schema)
    # Audit 2026-11-16 r2-optimuslar-be-05: with no `organization_id` table this scan checked
    # nothing and could never fail (optimuslar copied it although its ownership is per user).
    # Report SKIPPED (never a silent green PASS) when the schema has no tenant tables. The starter
    # template legitimately has none yet (apps add `organizations`); apps whose ownership is per
    # user (e.g. optimuslar: realtor_id/owner_user_id) must NOT carry this file at all.
    if not tenant:
        pytest.skip(
            "db/schema.sql has no table with an organization_id column: this guard checks nothing. "
            "User-owned apps must delete tests/test_tenancy_guard.py; if tenancy was renamed, update "
            "TENANT_COLUMN in the central source and re-copy."
        )
    violations: list[Violation] = []
    for path in backend_files():
        rel = str(path.relative_to(BACKEND_DIR))
        violations += scan_source(path.read_text(encoding="utf-8"), rel, tenant, children)
    assert not violations, (
        "SQL on a tenant table without an organization_id predicate (cross-tenant leak). Filter by "
        "organization_id, or add `tenant-ok: <why>` when the statement is safe:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_guard_flags_lookup_by_primary_key_only() -> None:
    assert synthetic('    return await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1", vid)')
    assert synthetic('    await conn.execute("DELETE FROM vehicles WHERE id = $1", vid)')
    assert synthetic(
        '    await conn.execute("UPDATE vehicles SET plate = $2 WHERE id = $1", vid, 1)'
    )


def test_guard_accepts_scoped_statements() -> None:
    scoped = [
        '    return await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1 AND organization_id = $2", vid, org)',
        '    return await conn.fetch("SELECT v.* FROM vehicles v WHERE v.organization_id = $1", org)',
        '    await conn.execute("UPDATE vehicles SET plate = $3 WHERE organization_id = $1 AND id = $2", org, vid, 1)',
        # table reached through a join to a row that is already scoped
        '    return await conn.fetch("SELECT s.* FROM visits s JOIN vehicles v ON v.id = s.vehicle_id '
        'WHERE v.organization_id = $1", org)',
        # dynamic WHERE built from a fragment of the same function
        '    where = ["organization_id = $1"]\n'
        "    return await conn.fetch(f\"SELECT * FROM vehicles WHERE {' AND '.join(where)}\", org)",
        # module-less INSERT ... VALUES carries its own organization_id
        '    await conn.execute("INSERT INTO vehicles (organization_id, plate) VALUES ($1, $2)", org, "A")',
        # a table outside the tenant set is never flagged
        '    return await conn.fetch("SELECT * FROM countries WHERE id = $1", vid)',
    ]
    for body in scoped:
        assert synthetic(body) == [], body


def test_guard_flags_partial_scope_and_unscoped_join() -> None:
    # visits is joined to nothing scoped: the organization filter protects only `vehicles`
    sql = (
        '    return await conn.fetch("SELECT * FROM vehicles v CROSS JOIN visits s WHERE s.id = $2 '
        'AND v.organization_id = $1", org, vid)'
    )
    flagged = synthetic(sql)
    assert flagged
    assert flagged[0].tables == ("visits",)


def test_guard_follows_joins_and_correlated_subqueries_to_a_scoped_row() -> None:
    chained = (
        '    return await conn.fetch("SELECT s.* FROM visits s JOIN countries c ON c.id = s.country_id '
        'JOIN vehicles v ON v.id = c.vehicle_id WHERE v.organization_id = $1", org)'
    )
    assert synthetic(chained) == []
    correlated = (
        '    return await conn.fetch("SELECT v.* FROM vehicles v WHERE v.organization_id = $1 '
        'AND EXISTS (SELECT 1 FROM visits s WHERE s.vehicle_id::text = v.id::text)", org)'
    )
    assert synthetic(correlated) == []
    unrelated = (
        '    return await conn.fetch("SELECT v.* FROM vehicles v WHERE v.organization_id = $1 '
        'AND EXISTS (SELECT 1 FROM visits s WHERE s.kind = $2)", org, vid)'
    )
    assert [v.tables for v in synthetic(unrelated)] == [("visits",)]


def test_guard_honours_the_tenant_ok_marker() -> None:
    on_line = '    row = await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1", vid)  # tenant-ok: id from a scoped list'
    in_sql = '    row = await conn.fetchrow("""\n    SELECT * FROM vehicles WHERE id = $1 -- tenant-ok: public\n    """, vid)'
    above = '    # tenant-ok: caller resolved vid under the org\n    row = await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1", vid)'
    for body in (on_line, in_sql, above):
        assert synthetic(body) == [], body
    on_def = (
        "# tenant-ok: platform-wide sweep\nasync def sweep(conn):\n"
        '    return await conn.fetch("SELECT * FROM vehicles")\n'
    )
    assert scan_source(on_def, "x_repository.py", SYNTHETIC_TENANT) == []
    assert synthetic(
        '    return await conn.fetch("SELECT * FROM vehicles")  # tenant-ok:'
    )  # empty reason fails


def test_schema_parser_finds_tenant_tables() -> None:
    schema = (
        "CREATE TABLE public.vehicles (\n    id uuid NOT NULL,\n    organization_id uuid NOT NULL\n);\n"
        "CREATE TABLE public.countries (\n    id uuid NOT NULL\n);\n"
    )
    assert tenant_tables_from_schema(schema) == frozenset({"vehicles"})


def test_guard_flags_organization_id_that_is_only_selected_or_returned() -> None:
    """Gap 2026-11-14: `SELECT {COLUMNS} FROM t WHERE id = $1` where COLUMNS lists organization_id
    counted as scoped. Selecting/returning the column is not a predicate."""
    listed = (
        '    cols = "id, organization_id, plate"\n'
        '    return await conn.fetchrow(f"SELECT {cols} FROM vehicles WHERE id = $1", vid)'
    )
    assert synthetic(listed)
    assert synthetic(
        '    return await conn.fetchrow("SELECT id, organization_id FROM vehicles WHERE id = $1", vid)'
    )
    assert synthetic(
        '    return await conn.fetchrow("UPDATE vehicles SET plate = $2 WHERE id = $1 '
        'RETURNING organization_id", vid, 1)'
    )
    # a real predicate next to a listed column still scopes
    assert not synthetic(
        '    return await conn.fetchrow("SELECT id, organization_id FROM vehicles '
        'WHERE id = $1 AND organization_id = $2", vid, org)'
    )


def test_guard_sees_schema_qualified_tables() -> None:
    schema = (
        "CREATE TABLE someschema.sometable (\n    id uuid NOT NULL,\n    organization_id uuid\n);\n"
    )
    tenant = tenant_tables_from_schema(schema)
    assert tenant == frozenset({"sometable"})
    source = 'async def f(conn, i):\n    return await conn.fetchrow("SELECT * FROM someschema.sometable WHERE id = $1", i)\n'
    assert scan_source(source, "x_repository.py", tenant)
    quoted = 'async def f(conn, i):\n    return await conn.fetchrow(\'SELECT * FROM "someschema"."sometable" WHERE id = $1\', i)\n'
    assert scan_source(quoted, "x_repository.py", tenant)


def test_guard_judges_a_where_less_fragment_where_it_is_completed() -> None:
    fragment_ok = (
        '_SEL = "SELECT v.id FROM vehicles v"\n'
        "async def load(conn, org):\n"
        '    return await conn.fetch(f"{_SEL} WHERE v.organization_id = $1", org)\n'
    )
    assert scan_source(fragment_ok, "x_repository.py", SYNTHETIC_TENANT) == []
    fragment_bad = fragment_ok.replace(" WHERE v.organization_id = $1", " WHERE v.id = $1")
    assert scan_source(fragment_bad, "x_repository.py", SYNTHETIC_TENANT)
    # a where-less constant that is executed as-is is still checked
    whole = '_ALL = "SELECT v.id FROM vehicles v"\nasync def load(conn):\n    return await conn.fetch(_ALL)\n'
    assert scan_source(whole, "x_repository.py", SYNTHETIC_TENANT)


SYNTHETIC_SCHEMA = (
    "CREATE TABLE public.vehicles (\n    id uuid NOT NULL,\n    organization_id uuid NOT NULL\n);\n"
    "CREATE TABLE public.visit_items (\n    id uuid NOT NULL,\n    vehicle_id uuid\n);\n"
    "CREATE TABLE public.visit_item_notes (\n    id uuid NOT NULL,\n    item_id uuid\n);\n"
    "CREATE TABLE public.countries (\n    id uuid NOT NULL\n);\n"
    "ALTER TABLE ONLY public.visit_items\n"
    "    ADD CONSTRAINT visit_items_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(id);\n"
    "ALTER TABLE ONLY public.visit_item_notes\n"
    "    ADD CONSTRAINT notes_item_fkey FOREIGN KEY (item_id) REFERENCES public.visit_items(id);\n"
    "ALTER TABLE ONLY public.countries\n"
    "    ADD CONSTRAINT countries_x_fkey FOREIGN KEY (id) REFERENCES public.users(id);\n"
)
SYNTHETIC_CHILDREN = child_tables_from_schema(SYNTHETIC_SCHEMA)


def synthetic_child(sql_body: str) -> list[Violation]:
    source = f"async def load(conn, org, vid):\n{sql_body}\n"
    return scan_source(source, "x_repository.py", SYNTHETIC_TENANT, SYNTHETIC_CHILDREN)


def test_child_tables_are_derived_transitively_and_exclude_reference_tables() -> None:
    assert frozenset({"visit_items", "visit_item_notes"}) == SYNTHETIC_CHILDREN


def test_guard_flags_child_table_by_id_write_and_transitive_child() -> None:
    assert synthetic_child(
        '    await conn.execute("UPDATE visit_items SET vehicle_id = $2 WHERE id = $1", vid, vid)'
    )
    assert synthetic_child('    await conn.execute("DELETE FROM visit_items WHERE id = $1", vid)')
    flagged = synthetic_child(
        '    return await conn.fetch("SELECT * FROM visit_item_notes WHERE item_id = $1", vid)'
    )
    assert [v.tables for v in flagged] == [("visit_item_notes",)]


def test_guard_accepts_child_statement_with_parent_org_check_or_reference_table() -> None:
    clean = [
        '    await conn.execute("UPDATE visit_items SET vehicle_id = $2 WHERE id = $1 AND EXISTS '
        '(SELECT 1 FROM vehicles v WHERE v.id = visit_items.vehicle_id AND v.organization_id = $3)", vid, vid, org)',
        '    return await conn.fetch("SELECT n.* FROM visit_item_notes n JOIN visit_items i ON i.id = n.item_id '
        'JOIN vehicles v ON v.id = i.vehicle_id AND v.organization_id = $2 WHERE n.item_id = $1", vid, org)',
        '    return await conn.fetch("SELECT * FROM countries WHERE id = $1", vid)',
        '    await conn.execute("DELETE FROM visit_items WHERE id = $1", vid)  # tenant-ok: purge job over every org',
    ]
    for body in clean:
        assert synthetic_child(body) == [], body
