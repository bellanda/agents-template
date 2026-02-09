import importlib
from typing import Any

from config.checkpointer import get_checkpointer
from config.paths import BASE_DIR

agents_registry: dict[str, Any] = {}


def discover_agents() -> dict[str, Any]:
    """Discover all LangChain/LangGraph agents located under agents in BASE_DIR.

    This is now called only once at startup for maximum speed.
    """
    agents: dict[str, Any] = {}
    agents_path = BASE_DIR / "agents"

    if not agents_path.exists():
        return agents

    checkpointer = get_checkpointer()

    for agent_dir in agents_path.iterdir():
        if agent_dir.is_dir() and (agent_dir / "agent.py").exists():
            module_path = f"agents.{agent_dir.name}.agent"
            try:
                agent_module = importlib.import_module(module_path)

                factory = getattr(agent_module, "create_root_agent", None)
                pre_built = getattr(agent_module, "root_agent", None)

                if factory is None and pre_built is None:
                    continue

                model_id = f"{agent_dir.name}".replace("_", "-")
                agent_name = getattr(agent_module, "AGENT_NAME", agent_dir.name)
                agent_description = getattr(agent_module, "AGENT_DESCRIPTION", f"Agent: {agent_dir.name}")
                agent_mode = getattr(agent_module, "AGENT_MODE", "single-shot")
                agent_suggestions = getattr(agent_module, "AGENT_SUGGESTIONS", [])

                if factory is not None:
                    cp = checkpointer if agent_mode == "chat" else None
                    agent = factory(checkpointer=cp)
                else:
                    agent = pre_built

                agents[model_id] = {
                    "agent": agent,
                    "name": agent_name,
                    "description": agent_description,
                    "mode": agent_mode,
                    "suggestions": agent_suggestions,
                }
                print(f"✓ Agent Loaded: {model_id}")
            except Exception as e:
                print(f"✗ Failed to load agent {agent_dir.name}: {e}")

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
