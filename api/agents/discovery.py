import importlib
from pathlib import Path
from typing import Any, Dict

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService


def discover_agents(session_service: InMemorySessionService) -> Dict[str, Any]:
    """Discover all agents in google_agents and langchain_agents directories."""
    agents = {}

    # Discover Google agents
    google_path = Path("google_agents")
    if google_path.exists():
        for agent_dir in google_path.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
                agent_file = agent_dir / "agent.py"
                if agent_file.exists():
                    try:
                        module_path = f"google_agents.{agent_dir.name}.agent"
                        agent_module = importlib.import_module(module_path)

                        if hasattr(agent_module, "root_agent"):
                            agent = agent_module.root_agent
                            model_id = f"google-{agent_dir.name}".replace("_", "-")
                            runner = Runner(agent=agent, app_name=f"{agent_dir.name}_app", session_service=session_service)

                            agents[model_id] = {
                                "agent": agent,
                                "runner": runner,
                                "name": agent.name,
                                "description": agent.description,
                                "agent_dir": agent_dir.name,
                                "type": "google",
                            }
                            print(f"✓ Google agent: {model_id}")
                    except Exception as e:
                        print(f"✗ Failed to load Google agent {agent_dir.name}: {e}")

    # Discover LangChain agents
    langchain_path = Path("langchain_agents")
    if langchain_path.exists():
        for agent_dir in langchain_path.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
                agent_file = agent_dir / "agent.py"
                if agent_file.exists():
                    try:
                        module_path = f"langchain_agents.{agent_dir.name}.agent"
                        agent_module = importlib.import_module(module_path)

                        if hasattr(agent_module, "root_agent"):
                            agent = agent_module.root_agent
                            model_id = f"langchain-{agent_dir.name}".replace("_", "-")
                            agent_name = getattr(agent_module, "AGENT_NAME", agent_dir.name)
                            agent_description = getattr(
                                agent_module, "AGENT_DESCRIPTION", f"LangChain agent: {agent_dir.name}"
                            )

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
