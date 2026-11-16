"""The template's exceptions speak the fleet vocabulary (drift-backend-07, audit 2026-11-13).

The agents layer is synced into apps that already own `api/core/exceptions.py`; if the synced code
imports a name the apps do not define, the backend fails to boot. Every exception name used by the
template's synced layers must be one the fleet defines, and must take `detail=` by keyword.
"""

import ast
from pathlib import Path

import pytest

from api.core import exceptions

BACKEND_DIR = Path(__file__).resolve().parents[2]
SYNCED_LAYERS = (
    "src/api/schemas/agents",
    "src/api/models/agents",
    "src/api/repositories/agents",
    "src/api/services/agents",
    "src/api/routes/agents",
    "src/api/routes/uploads.py",
    "src/api/services/auth.py",
    "config/uploads.py",
)
# What every app defines in its own api/core/exceptions.py (kailos is the reference).
FLEET_EXCEPTIONS = frozenset(
    {
        "AuthenticationError",
        "BadRequestError",
        "ForbiddenError",
        "DoesNotExistError",
        "ConflictError",
        "RateLimitError",
    }
)


def _synced_files() -> list[Path]:
    files: list[Path] = []
    for entry in SYNCED_LAYERS:
        path = BACKEND_DIR / entry
        files += sorted(path.rglob("*.py")) if path.is_dir() else [path]
    return files


def test_synced_layers_import_only_fleet_exception_names() -> None:
    offenders = []
    for path in _synced_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "api.core.exceptions":
                offenders += [
                    f"{path.relative_to(BACKEND_DIR)}: {alias.name}"
                    for alias in node.names
                    if alias.name not in FLEET_EXCEPTIONS
                ]
    assert not offenders, f"names the apps do not define (ImportError after sync): {offenders}"


def test_synced_layers_pass_detail_by_keyword() -> None:
    offenders = []
    for path in _synced_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            is_call = isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            if is_call and node.func.id in FLEET_EXCEPTIONS and node.args:
                offenders.append(f"{path.relative_to(BACKEND_DIR)}:{node.lineno} {node.func.id}")
    assert not offenders, f"positional message (apps read it as `type`): {offenders}"


@pytest.mark.parametrize(
    ("name", "status_code"),
    [
        ("AuthenticationError", 401),
        ("BadRequestError", 400),
        ("ForbiddenError", 403),
        ("DoesNotExistError", 404),
        ("ConflictError", 409),
        ("RateLimitError", 429),
    ],
)
def test_exceptions_carry_status_and_custom_detail(name: str, status_code: int) -> None:
    error = getattr(exceptions, name)(detail="mensagem")
    assert (error.status_code, error.detail) == (status_code, "mensagem")
    assert getattr(exceptions, name)().detail
