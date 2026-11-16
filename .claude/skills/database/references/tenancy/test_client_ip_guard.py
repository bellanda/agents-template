"""Guard: nobody reads `X-Forwarded-For` for an IP that is stored or throttled.

nginx appends to the client's own `X-Forwarded-For` (`$proxy_add_x_forwarded_for`), so its FIRST
element is whatever the caller typed. Only `X-Real-IP` (= `$remote_addr`, already restored from
Cloudflare by the realip module) is trustworthy. promoservice stored the first XFF element as the
legal evidence of a quote approval (audit 2026-11-13 core-security-05): anyone could write the IP
they wanted. The single correct reader is `api/core/client_ip.py` (and, in apps that still have
it, `client_ip_from_scope` in the logging middleware, which ignores XFF).
"""

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FORBIDDEN_HEADER = "x-forwarded-for"
ALLOWED_FILES = frozenset({"client_ip.py"})
SKIPPED_DIR_NAMES = frozenset({".venv", "__pycache__", "node_modules"})


def forwarded_for_reads(source: str) -> list[int]:
    """Lines where the header name appears as a string/bytes literal (comments do not count)."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Constant):
            continue
        value = node.value.decode("latin-1") if isinstance(node.value, bytes) else node.value
        if isinstance(value, str) and value.strip().lower() == FORBIDDEN_HEADER:
            lines.append(node.lineno)
    return lines


def test_no_code_reads_x_forwarded_for_outside_the_client_ip_helper() -> None:
    offenders = []
    for path in sorted((BACKEND_DIR / "src").rglob("*.py")):
        if path.name in ALLOWED_FILES or SKIPPED_DIR_NAMES & set(path.parts):
            continue
        offenders += [
            f"{path.relative_to(BACKEND_DIR)}:{line}"
            for line in forwarded_for_reads(path.read_text(encoding="utf-8"))
        ]
    assert not offenders, (
        "X-Forwarded-For is client-controlled; use api.core.client_ip.client_ip(request) or "
        f"request_evidence(request): {offenders}"
    )


def test_guard_catches_a_forged_header_read() -> None:
    assert forwarded_for_reads('ip = request.headers.get("X-Forwarded-For")') == [1]
    assert forwarded_for_reads('headers = {b"x-forwarded-for": b"1.1.1.1"}') == [1]
    assert forwarded_for_reads('ip = request.headers.get("x-real-ip")  # x-forwarded-for') == []
