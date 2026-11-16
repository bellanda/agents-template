"""No route that returns a `StreamingResponse` may hold a pooled connection for the whole stream.

`get_conn` is a `yield` dependency: FastAPI closes it only AFTER the response is fully sent, so a
route that both depends on it and returns a `StreamingResponse` keeps one of the pool's `max_size`
connections for the life of the stream. An SSE inbox lives for hours: ~130 open tabs (8 workers x
16) exhaust the pool and every other screen waits `pool.timeout` then errors, with no error on
the server (audit 2026-11-13 core-performance-01).

Fix pattern: resolve org/permission with a SHORT `async with pool.acquire()` (or
`Depends(get_conn_scope)` / `db_scope(None)()`) and give the generator only the pool/`db_scope`.

Fleet test (identical in every backend). Static, so it also guards routes written later.
"""

import ast
from pathlib import Path

ROUTES_DIR = Path(__file__).resolve().parents[2] / "src" / "api" / "routes"

# "<path relative to routes/>::<function>": reason. Adding an entry needs a comment that says why
# holding the connection is bounded, and who owns the migration to the scoped pattern.
ALLOWED: dict[str, str] = {}


def _depends_on_get_conn(fn: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    return "Depends(get_conn)" in ast.unparse(fn.args)


def _returns_streaming_response(fn: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    source = ast.unparse(fn)
    # `sse_response(` is the template's helper that builds the StreamingResponse.
    return "StreamingResponse(" in source or "sse_response(" in source


def test_streaming_routes_do_not_depend_on_get_conn():
    offenders: list[str] = []
    for path in sorted(ROUTES_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
                continue
            if _depends_on_get_conn(node) and _returns_streaming_response(node):
                key = f"{path.relative_to(ROUTES_DIR).as_posix()}::{node.name}"
                if key not in ALLOWED:
                    offenders.append(key)
    assert not offenders, (
        "These routes return a StreamingResponse but depend on get_conn (the pooled connection "
        f"stays checked out until the stream ends): {offenders}. Use a short pool.acquire() / "
        "get_conn_scope and pass the generator only the pool."
    )


def test_allowlist_has_no_stale_entries():
    present = set()
    for path in ROUTES_DIR.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and _depends_on_get_conn(
                node
            ):
                present.add(f"{path.relative_to(ROUTES_DIR).as_posix()}::{node.name}")
    assert set(ALLOWED) <= present, f"stale allowlist entries: {set(ALLOWED) - present}"
