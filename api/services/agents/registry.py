from typing import Any, Dict

from api.services.agents.discovery import discover_agents

agents_registry: Dict[str, Any] = {}


def _ensure_agents_loaded() -> None:
    """Lazy-load agents into the registry if it is empty."""
    global agents_registry
    if agents_registry:
        return
    agents_registry = discover_agents()


def get_agents_registry() -> Dict[str, Any]:
    """FastAPI dependency to retrieve the current in-memory agents registry."""
    _ensure_agents_loaded()
    return agents_registry


def set_agents_registry(new_registry: Dict[str, Any]) -> None:
    """Replace the in-memory registry (used on startup and reload)."""
    global agents_registry
    agents_registry = new_registry
