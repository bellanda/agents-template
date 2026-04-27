import importlib
from typing import Any

from api.core.agents.callbacks import usage_recorder
from api.core.agents.checkpointer import get_checkpointer
from api.core.agents.schemas import serialize_suggestions_for_api
from config import paths

agents_registry: dict[str, Any] = {}


def discover_agents() -> dict[str, Any]:
    """Discover all LangChain/LangGraph agents located under agents in BASE_DIR.

    This is now called only once at startup for maximum speed.
    """
    agents: dict[str, Any] = {}
    agents_path = paths.BASE_DIR / "agents"

    if not agents_path.exists():
        return agents

    checkpointer = get_checkpointer()

    for agent_dir in agents_path.iterdir():
        if not (agent_dir.is_dir() and (agent_dir / "agent.py").exists()):
            continue

        module_path = f"agents.{agent_dir.name}.agent"
        try:
            agent_module = importlib.import_module(module_path)

            factory = getattr(agent_module, "create_root_agent", None)
            pre_built = getattr(agent_module, "root_agent", None)

            if factory is None and pre_built is None:
                continue

            agent_config = getattr(agent_module, "config", None)
            if agent_config is None:
                continue

            model_id = agent_dir.name.replace("_", "-")

            # Use the save_to_db flag from the config to decide if we pass a checkpointer
            cp = checkpointer if (agent_config.save_to_db and factory is not None) else None
            agent = factory(checkpointer=cp) if factory is not None else pre_built

            # Single global callback persists agent_message_usage for ANY invocation path.
            agent = agent.with_config(callbacks=[usage_recorder])

            agents[model_id] = {
                "agent": agent,
                "name": agent_config.name,
                "description": agent_config.description,
                "suggestions": serialize_suggestions_for_api(agent_config.suggestions),
                "save_to_db": agent_config.save_to_db,
            }
        except Exception:
            pass

    return agents


async def reload_agents_registry() -> None:
    """Reload all agents (called at startup)."""
    global agents_registry
    agents_registry = discover_agents()


def get_agents_registry() -> dict[str, Any]:
    """FastAPI dependency to retrieve the current in-memory agents registry."""
    return agents_registry


def set_agents_registry(new_registry: dict[str, Any]) -> None:
    """Replace the in-memory registry."""
    global agents_registry
    agents_registry = new_registry
