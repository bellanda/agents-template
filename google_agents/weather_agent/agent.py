import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))


from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from google_agents.weather_agent.tools import get_weather

root_agent = Agent(
    name="weather_agent_litellm",
    model=LiteLlm(
        model="ollama_chat/qwen3:4b",
        temperature=0.3,
        stream=True,
    ),
    description="Provides weather information using LiteLLM proxy.",
    instruction="You are a helpful weather assistant. "
    "Use the 'get_weather' tool for city weather requests. "
    "Present information clearly and in a friendly manner. "
    "If the user asks about weather, always use the tool to get current information.",
    tools=[get_weather],
)
