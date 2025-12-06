from typing import Any, Dict

agents_registry: Dict[str, Any] = {}


def get_agents_registry() -> Dict[str, Any]:
    """FastAPI dependency to retrieve the current in-memory agents registry."""
    return agents_registry


def set_agents_registry(new_registry: Dict[str, Any]) -> None:
    """Replace the in-memory registry (used on startup and reload)."""
    global agents_registry
    agents_registry = new_registry
