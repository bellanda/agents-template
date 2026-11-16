"""`discover_agents` must not swallow a broken agent module (audit 2026-11
r2-kailos-be-portals-messaging-05): it logs with the traceback and fails the startup."""

import sys

import pytest
from structlog.testing import capture_logs

from api.services.agents import registry
from config import paths


def test_broken_agent_module_is_logged_and_fails_discovery(tmp_path, monkeypatch):
    agent_dir = tmp_path / "agents" / "zz_broken_discovery_agent"
    agent_dir.mkdir(parents=True)
    (tmp_path / "agents" / "__init__.py").write_text("")
    (agent_dir / "agent.py").write_text("raise ImportError('boom from the upgrade')\n")
    monkeypatch.setattr(paths, "BASE_DIR", tmp_path)
    monkeypatch.setattr(registry, "get_checkpointer", lambda: None)
    monkeypatch.syspath_prepend(str(tmp_path))
    # `agents` may already be imported from the real tree (apps): make the tmp one resolvable too.
    pkg = sys.modules.get("agents")
    if pkg is not None and hasattr(pkg, "__path__"):
        monkeypatch.setattr(pkg, "__path__", [*pkg.__path__, str(tmp_path / "agents")])

    with capture_logs() as logs, pytest.raises(ImportError, match="boom"):
        registry.discover_agents()

    failed = [e for e in logs if e["event"] == "agent_discovery_failed"]
    assert failed and failed[0]["agent"] == "zz_broken_discovery_agent"
    assert failed[0]["log_level"] == "error"
