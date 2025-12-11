import importlib
from typing import Any, Dict

from environment.paths import BASE_DIR

agents_registry: Dict[str, Any] = {}


def discover_agents() -> Dict[str, Any]:
    """Discover all LangChain/LangGraph agents located under agents in BASE_DIR."""
    agents: Dict[str, Any] = {}
    agents_path = BASE_DIR / "agents"

    if not agents_path.exists():
        print(f"✗ agents directory not found at {agents_path}")
        return agents

    for agent_dir in agents_path.iterdir():
        if agent_dir.is_dir() and (agent_dir / "agent.py").exists():
            module_path = f"agents.{agent_dir.name}.agent"
            try:
                agent_module = importlib.import_module(module_path)

                if hasattr(agent_module, "root_agent"):
                    agent = agent_module.root_agent
                    model_id = f"{agent_dir.name}".replace("_", "-")
                    agent_name = getattr(agent_module, "AGENT_NAME", agent_dir.name)
                    agent_description = getattr(agent_module, "AGENT_DESCRIPTION", f"Agent: {agent_dir.name}")

                    agents[model_id] = {
                        "agent": agent,
                        "name": agent_name,
                        "description": agent_description,
                    }
                    print(f"✓ Agent: {model_id}")
            except Exception as e:
                print(f"✗ Failed to load agent {agent_dir.name}: {e}")

    return agents


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
