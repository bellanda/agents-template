# LangChain Agents

This directory contains agents implemented using the LangChain framework, which are automatically discovered and served by the FastAPI server with OpenAI-compatible endpoints.

## Structure

Each agent must follow this structure:

```
langchain_agents/
├── agent_name/
│   ├── agent.py          # Main file with root_agent variable
│   └── tools/            # Tools directory (optional)
│       ├── __init__.py
│       ├── tool1.py
│       └── tool2.py
```

## Agent Example

The agent must be defined in the `agent.py` file and export a variable called `root_agent`:

```python
from langchain.agents import AgentType, initialize_agent
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage

# Configure the model
llm = ChatOpenAI(
    model="gpt-4",
    openai_api_base="https://api.company.ai/v1",
    openai_api_key="your-key-here",
    temperature=0.3,
)

# Create the agent
root_agent = initialize_agent(
    tools=[],  # Your tools here
    llm=llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    verbose=True,
)

# Required attributes for compatibility
root_agent.name = "agent_name"
root_agent.description = "Agent description"
```

## API Configuration

To use a custom company API, configure the `ChatOpenAI` with:

- `openai_api_base`: "https://api.company.ai/v1"
- `openai_api_key`: Your API key
- `model`: Available model in the API

## Tools

Tools must inherit from `BaseTool` from LangChain:

```python
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class MyToolInput(BaseModel):
    parameter: str = Field(description="Parameter description")

class MyTool(BaseTool):
    name = "my_tool"
    description = "Tool description"
    args_schema = MyToolInput

    def _run(self, parameter: str) -> str:
        # Tool implementation
        return "result"

    async def _arun(self, parameter: str) -> str:
        return self._run(parameter)

# Instance for use
my_tool = MyTool()
```

## Automatic Discovery

The system automatically:

1. Scans the `langchain_agents/` directory
2. Looks for subdirectories with `agent.py`
3. Imports the `root_agent` from each file
4. Registers the agent with ID `langchain-{directory_name}`
5. Makes it available via REST API and OpenAI-compatible endpoints

## API Usage

Once configured, the agent will be available at:

- **Direct chat**: `POST /chat` with `model: "langchain-agent-name"`
- **OpenAI compatible**: `POST /v1/chat/completions` with `model: "langchain-agent-name"`
- **Model list**: `GET /v1/models`

## Available LLM Providers

The template supports multiple LLM providers configured in the `llms/` directory:

### Groq Configuration

```python
from langchain_groq import ChatGroq

llm = ChatGroq(
    model="llama3-8b-8192",
    groq_api_key="your-groq-api-key",
    temperature=0.3,
)
```

### NVIDIA Configuration

```python
from langchain_nvidia_ai_endpoints import ChatNVIDIA

llm = ChatNVIDIA(
    model="meta/llama3-70b-instruct",
    nvidia_api_key="your-nvidia-api-key",
    temperature=0.3,
)
```

### OpenAI Configuration

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4",
    openai_api_key="your-openai-api-key",
    temperature=0.3,
)
```

## Example Agents

The template includes example agents:

### Web Search Agent

Located in `langchain_agents/web_search_agent/`:

- Uses DuckDuckGo search tool
- Provides web search capabilities
- Formats search results for users

### Weather Agent

Located in `langchain_agents/weather_agent/`:

- Provides weather information
- Uses weather API integration
- Returns formatted weather data

## Tool Development

### Creating Custom Tools

1. Create a new file in the `tools/` directory
2. Define your tool class inheriting from `BaseTool`
3. Implement the `_run` and `_arun` methods
4. Import and add to your agent's tools list

Example tool structure:

```python
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field

class CustomToolInput(BaseModel):
    query: str = Field(description="The input query for the tool")

class CustomTool(BaseTool):
    name = "custom_tool"
    description = "Useful for custom operations"
    args_schema: Type[BaseModel] = CustomToolInput
    return_direct = False  # Set to True if tool output should be returned directly

    def _run(self, query: str, run_manager: Optional = None) -> str:
        """Execute the tool synchronously."""
        # Your tool logic here
        return f"Result for: {query}"

    async def _arun(self, query: str, run_manager: Optional = None) -> str:
        """Execute the tool asynchronously."""
        return self._run(query, run_manager)
```

## Agent Configuration Options

### Memory Configuration

```python
from langchain.memory import ConversationBufferWindowMemory

memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    k=10,  # Keep last 10 exchanges
    return_messages=True
)

root_agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    memory=memory,
    verbose=True,
)
```

### System Message Configuration

```python
from langchain.schema import SystemMessage

system_message = SystemMessage(
    content="You are a helpful assistant specialized in..."
)

root_agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    system_message=system_message,
    verbose=True,
)
```

## Best Practices

1. **Tool Naming**: Use descriptive, unique names for tools
2. **Error Handling**: Implement proper error handling in tools
3. **Documentation**: Provide clear descriptions for tools and parameters
4. **Testing**: Test tools independently before integrating
5. **Performance**: Consider async implementations for I/O operations
6. **Security**: Validate inputs and sanitize outputs
7. **Logging**: Use appropriate logging for debugging

## Debugging

### Enable Verbose Mode

Set `verbose=True` in your agent configuration to see detailed execution logs.

### Tool Testing

Test individual tools before adding them to agents:

```python
from your_agent.tools.my_tool import MyTool

tool = MyTool()
result = tool.run("test input")
print(result)
```

### Agent Testing

Test agents directly:

```python
from langchain_agents.your_agent.agent import root_agent

response = root_agent.run("Hello, how can you help me?")
print(response)
```

## Integration with Main Application

Agents are automatically integrated with the main FastAPI application:

1. **Discovery**: Agents are discovered on server startup
2. **Registration**: Each agent gets a unique model ID
3. **API Exposure**: Available through OpenAI-compatible endpoints
4. **Session Management**: Built-in conversation session handling
5. **Streaming**: Real-time response streaming support

## Complete Example

Here's a complete example of a LangChain agent with custom tools:

```python
# langchain_agents/example_agent/agent.py

from langchain.agents import AgentType, initialize_agent
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferWindowMemory
from .tools.calculator import CalculatorTool
from .tools.search import SearchTool

# Configure LLM
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.3,
)

# Configure memory
memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    k=10,
    return_messages=True
)

# Initialize tools
tools = [
    CalculatorTool(),
    SearchTool(),
]

# Create agent
root_agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    memory=memory,
    verbose=True,
    handle_parsing_errors=True,
)

# Required attributes
root_agent.name = "example_agent"
root_agent.description = "An example agent with calculator and search capabilities"

# Optional: Agent constants for the discovery system
AGENT_NAME = "Example Agent"
AGENT_DESCRIPTION = "A comprehensive example agent demonstrating tool usage and conversation handling"
```

This agent will be automatically discovered and available as `langchain-example-agent` in the API.
