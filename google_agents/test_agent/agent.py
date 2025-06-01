import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))


from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

root_agent = Agent(
    name="test_agent",
    model=LiteLlm(
        model="ollama_chat/qwen3:4b",
        temperature=0.3,
        stream=True,
    ),
    description="Test agent",
    instruction="You are a helpful test assistant. "
    "Present information clearly and in a friendly manner. "
    "If the user asks about test, always use the tool to get current information.",
    tools=[],
)
