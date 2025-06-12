import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))


from google.adk.agents import Agent

from google_agents.weather_agent.tools import get_weather

root_agent = Agent(
    name="weather_agent_litellm",
    model="gemini-2.5-flash-preview-05-20",
    description="Provides weather information using LiteLLM proxy.",
    instruction="You are a helpful weather assistant. "
    "Use the 'get_weather' tool for city weather requests. "
    "Present information clearly and in a friendly manner. "
    "If the user asks about weather, always use the tool to get current information.",
    tools=[get_weather],
)
