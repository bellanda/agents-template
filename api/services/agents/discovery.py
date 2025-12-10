import importlib
from typing import Any, Dict

from environment.paths import BASE_DIR


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

    return agents


if __name__ == "__main__":
    discover_agents()
