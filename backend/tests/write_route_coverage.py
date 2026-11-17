"""Write-route coverage guard: every POST/PUT/PATCH/DELETE route has a test that SUCCEEDED on it.

Fleet canonical (shared-backend, byte-identical in every app). Born from the QUB5J53 incident
(kailos, 2026-11-17): a write path changed only a copy of the showroom price and no test noticed.
This guard is the floor of the CRUD contract in `rules/tests.md` ("Coverage por rota"): a write
route nobody ever called with a 2xx/3xx is a route nobody knows works. The QUALITY of each test
(re-read through what the screen reads) is reviewed by people; this only proves the call exists.

How it counts: `APIRoute.handle` is wrapped once at class level, so ANY test client counts (the
`client` fixture, ad-hoc `AsyncClient`, approval executors that call routes). Only 2xx/3xx
responses count: a test that only ever gets 403/422 does not prove the write works. The full path
comes from FastAPI's effective route context (0.163+: routers are not copied on include).

Modes, by env var `WRITE_ROUTE_COVERAGE` (unset = the plugin does nothing, so running a subset of
tests never fails because of it):
- `report`  : prints the write routes no test succeeded on, and stale baseline entries.
- `enforce` : (check.sh) fails the run when a route outside the baseline is uncovered, when a
              baseline route is now covered or no longer exists (the baseline only shrinks), or
              when a baseline entry has no reason.
- `update`  : rewrites the baseline with the uncovered routes, keeping the reasons already
              written; new entries get an empty reason that `enforce` rejects until filled.

Per app: `backend/tests/write_route_coverage_baseline.json` = {"PATCH /api/v1/...": "reason"}.
Under xdist each worker ships its hits through `workeroutput`; the controller merges and judges.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi import routing as fastapi_routing
from fastapi.routing import APIRoute, iter_route_contexts

__all__ = [
    "CoverageVerdict",
    "collect_write_routes",
    "evaluate_write_route_coverage",
    "install_write_route_recorder",
    "recorded_write_hits",
]

MODE_ENV_VAR = "WRITE_ROUTE_COVERAGE"
MODES = frozenset({"report", "enforce", "update"})
BASELINE_PATH = Path(__file__).with_name("write_route_coverage_baseline.json")
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
FIRST_SUCCESS_STATUS = 200
FIRST_CLIENT_ERROR_STATUS = 400
WORKER_OUTPUT_KEY = "write_route_coverage_hits"
APP_MODULE = "api.main"

recorded_write_hits: set[str] = set()
original_route_handle = APIRoute.handle


@dataclass(frozen=True)
class CoverageVerdict:
    uncovered_new: list[str] = field(default_factory=list)
    baseline_now_covered: list[str] = field(default_factory=list)
    baseline_vanished: list[str] = field(default_factory=list)
    baseline_missing_reason: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not (
            self.uncovered_new
            or self.baseline_now_covered
            or self.baseline_vanished
            or self.baseline_missing_reason
        )


def route_key(method: str, path: str) -> str:
    return f"{method} {path}"


def resolve_full_path(route: APIRoute, scope: Mapping) -> str:
    """Full prefixed path of the route serving this request (template, not the concrete URL)."""
    context = fastapi_routing._get_scope_effective_route_context(scope)
    if context is not None and context.original_route is route and context.path:
        return context.path
    return route.path


async def recording_route_handle(self: APIRoute, scope, receive, send) -> None:
    method = scope.get("method", "")
    if scope.get("type") != "http" or method not in WRITE_METHODS:
        await original_route_handle(self, scope, receive, send)
        return
    statuses: list[int] = []

    async def capture_status(message) -> None:
        if message["type"] == "http.response.start":
            statuses.append(message["status"])
        await send(message)

    await original_route_handle(self, scope, receive, capture_status)
    if statuses and FIRST_SUCCESS_STATUS <= statuses[0] < FIRST_CLIENT_ERROR_STATUS:
        recorded_write_hits.add(route_key(method, resolve_full_path(self, scope)))


def install_write_route_recorder() -> None:
    """Idempotent: wraps `APIRoute.handle` once for the whole process."""
    APIRoute.handle = recording_route_handle


def collect_write_routes(routes: Iterable) -> set[str]:
    """Every (write method, full path) the app exposes."""
    expected: set[str] = set()
    for context in iter_route_contexts(list(routes)):
        if not isinstance(context.original_route, APIRoute):
            continue
        for method in set(context.methods or ()) & WRITE_METHODS:
            expected.add(route_key(method, context.path))
    return expected


def evaluate_write_route_coverage(
    expected: set[str], hits: set[str], baseline: Mapping[str, str]
) -> CoverageVerdict:
    uncovered = expected - hits
    return CoverageVerdict(
        uncovered_new=sorted(uncovered - baseline.keys()),
        baseline_now_covered=sorted(key for key in baseline if key in expected and key in hits),
        baseline_vanished=sorted(key for key in baseline if key not in expected),
        baseline_missing_reason=sorted(
            key for key, reason in baseline.items() if key in uncovered and not reason.strip()
        ),
    )


def read_baseline() -> dict[str, str]:
    if not BASELINE_PATH.exists():
        return {}
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def write_baseline(expected: set[str], hits: set[str], baseline: Mapping[str, str]) -> int:
    uncovered = sorted(expected - hits)
    updated = {key: baseline.get(key, "") for key in uncovered}
    BASELINE_PATH.write_text(
        json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return len(updated)


def current_mode() -> str | None:
    mode = os.environ.get(MODE_ENV_VAR, "").strip().lower()
    if mode and mode not in MODES:
        raise pytest.UsageError(
            f"{MODE_ENV_VAR}={mode!r}: expected one of {sorted(MODES)} or unset"
        )
    return mode or None


def is_xdist_worker(config: pytest.Config) -> bool:
    return hasattr(config, "workerinput")


def pytest_configure(config: pytest.Config) -> None:
    if current_mode() is not None:
        install_write_route_recorder()


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error) -> None:
    recorded_write_hits.update(getattr(node, "workeroutput", {}).get(WORKER_OUTPUT_KEY, ()))


def format_section(
    title: str, keys: list[str], baseline: Mapping[str, str] | None = None
) -> list[str]:
    if not keys:
        return []
    lines = [f"  {title} ({len(keys)}):"]
    for key in keys:
        reason = f"  — {baseline[key]}" if baseline and baseline.get(key) else ""
        lines.append(f"    {key}{reason}")
    return lines


def render_verdict(verdict: CoverageVerdict, expected: set[str], hits: set[str]) -> list[str]:
    covered = len(expected & hits)
    lines = [f"write-route coverage: {covered}/{len(expected)} write routes with a successful test"]
    lines += format_section("UNCOVERED (not in baseline)", verdict.uncovered_new)
    lines += format_section("now covered: remove from baseline", verdict.baseline_now_covered)
    lines += format_section("no longer exist: remove from baseline", verdict.baseline_vanished)
    lines += format_section("baseline entry without reason", verdict.baseline_missing_reason)
    return lines


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    mode = current_mode()
    config = session.config
    if mode is None:
        return
    if is_xdist_worker(config):
        config.workeroutput[WORKER_OUTPUT_KEY] = sorted(recorded_write_hits)
        return
    if exitstatus != pytest.ExitCode.OK:
        return  # a red or interrupted run says nothing about coverage
    from importlib import import_module

    expected = collect_write_routes(import_module(APP_MODULE).app.routes)
    baseline = read_baseline()
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if mode == "update":
        count = write_baseline(expected, recorded_write_hits, baseline)
        reporter.ensure_newline()
        reporter.write_sep("-", f"write-route coverage: baseline rewritten with {count} routes")
        return
    verdict = evaluate_write_route_coverage(expected, recorded_write_hits, baseline)
    reporter.ensure_newline()
    reporter.write_sep("-", "write-route coverage")
    for line in render_verdict(verdict, expected, recorded_write_hits):
        reporter.write_line(line)
    if mode == "enforce" and not verdict.is_clean:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
