import importlib
from typing import Any, Dict

from environment.paths import BASE_DIR


def discover_agents() -> Dict[str, Any]:
    """Discover all LangChain/LangGraph agents located under langchain_agents in BASE_DIR."""
    agents: Dict[str, Any] = {}

    langchain_path = BASE_DIR / "langchain_agents"
    if not langchain_path.exists():
        print(f"✗ langchain_agents directory not found at {langchain_path}")
        return agents

    for agent_dir in langchain_path.iterdir():
        if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
            agent_file = agent_dir / "agent.py"
            if not agent_file.exists():
                continue

            try:
                module_path = f"langchain_agents.{agent_dir.name}.agent"
                agent_module = importlib.import_module(module_path)

                if hasattr(agent_module, "root_agent"):
                    agent = agent_module.root_agent
                    model_id = f"langchain-{agent_dir.name}".replace("_", "-")
                    agent_name = getattr(agent_module, "AGENT_NAME", agent_dir.name)
                    agent_description = getattr(agent_module, "AGENT_DESCRIPTION", f"LangChain agent: {agent_dir.name}")

                    agents[model_id] = {
                        "agent": agent,
                        "runner": None,
                        "name": agent_name,
                        "description": agent_description,
                        "agent_dir": agent_dir.name,
                        "type": "langchain",
                    }
                    print(f"✓ LangChain agent: {model_id}")
            except Exception as e:
                print(f"✗ Failed to load LangChain agent {agent_dir.name}: {e}")

    return agents
