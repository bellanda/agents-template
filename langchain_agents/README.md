# LangChain Agents

This directory contains agents implemented using **LangGraph** (the modern LangChain framework), which are automatically discovered and served by the FastAPI server with OpenAI-compatible endpoints.

## Structure

Each agent must follow this structure:

```
langchain_agents/
├── agent_name/
│   ├── agent.py          # Main file with root_agent variable
│   └── tools/            # Tools directory (optional)
│       ├── __init__.py   # Export tools
│       ├── tool1.py      # Individual tool files
│       └── tool2.py
```

## Modern LangGraph Agent Example

The agent must be defined in the `agent.py` file using **LangGraph's `create_react_agent`** and export a variable called `root_agent`:

```python
from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from environment import api_keys
from langchain_agents.your_agent.tools import your_tool

# Configure the LLM
llm = ChatGroq(
    model="llama3-70b-8192",
    api_key=api_keys.GROQ_API_KEY
)

# Configure available tools
tools = [your_tool]

# System message for the agent
system_message = SystemMessage(
    content="""You are an intelligent assistant specialized in [your domain].

MANDATORY INSTRUCTIONS:
- ALWAYS use the appropriate tool when the user asks for specific information
- NEVER invent information - use only data returned by tools
- Wait for the complete tool result before responding
- Provide detailed responses based on tool results
- Be polite and helpful

Process and improve the presentation of data returned by tools for the end user.
"""
)

# Configure memory (checkpointer)
memory = MemorySaver()

# Create the agent using LangGraph
root_agent = create_react_agent(
    llm,
    tools,
    prompt=system_message,
    checkpointer=memory
)

# Metadata for the discovery system
AGENT_NAME = "your_agent"
AGENT_DESCRIPTION = "LangGraph agent with [description] using Groq LLM"
```

## Tool Development with @tool Decorator

Tools are now created using the modern `@tool` decorator approach:

```python
from langchain.tools import tool
from pydantic import BaseModel, Field

class YourToolInput(BaseModel):
    """Input schema for your tool."""

    query: str = Field(description="Query parameter for the tool")

@tool("your_tool_name", args_schema=YourToolInput, return_direct=False)
def your_tool(query: str) -> str:
    """Tool description for the agent.

    Use this tool when you need to:
    - Perform specific operations
    - Get external data
    - Process information

    Args:
        query: The input query for the tool

    Returns:
        Formatted string with the tool results
    """
    try:
        # Your tool implementation here
        result = perform_operation(query)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {str(e)}"
```

## Tool Export Structure

Tools must be properly exported in the `tools/__init__.py` file:

```python
from .your_tool import your_tool

__all__ = ["your_tool"]
```

## Available LLM Providers

The template supports multiple LLM providers:

### Groq Configuration (Recommended)

```python
from langchain_groq import ChatGroq

llm = ChatGroq(
    model="llama3-70b-8192",  # or "meta-llama/llama-4-maverick-17b-128e-instruct"
    api_key=api_keys.GROQ_API_KEY,
    temperature=0.3,
)
```

### NVIDIA Configuration

```python
from langchain_nvidia_ai_endpoints import ChatNVIDIA

llm = ChatNVIDIA(
    model="meta/llama3-70b-instruct",
    nvidia_api_key=api_keys.NVIDIA_API_KEY,
    temperature=0.3,
)
```

### OpenAI Configuration

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4",
    openai_api_key=api_keys.OPENAI_API_KEY,
    temperature=0.3,
)
```

## Memory and State Management

LangGraph uses **MemorySaver** for conversation memory:

```python
from langgraph.checkpoint.memory import MemorySaver

# Configure memory (checkpointer)
memory = MemorySaver()

# Create agent with memory
root_agent = create_react_agent(
    llm,
    tools,
    prompt=system_message,
    checkpointer=memory
)
```

## System Message Configuration

Use **SystemMessage** from langchain_core for agent instructions:

```python
from langchain_core.messages import SystemMessage

system_message = SystemMessage(
    content="""You are a specialized assistant for [domain].

INSTRUCTIONS:
- Always use tools when needed
- Provide accurate information
- Format responses clearly
- Be helpful and professional

Additional context and guidelines...
"""
)
```

## Example Agents

### Web Search Agent

Located in `langchain_agents/web_search_agent/`:

```python
from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from environment import api_keys
from langchain_agents.web_search_agent.tools import web_search

llm = ChatGroq(
    model="meta-llama/llama-4-maverick-17b-128e-instruct",
    api_key=api_keys.GROQ_API_KEY
)

tools = [web_search]

system_message = SystemMessage(
    content="""You are an intelligent assistant specialized in web search.

MANDATORY INSTRUCTIONS:
- ALWAYS use the web_search tool when users ask about people, companies, events, or specific facts
- NEVER invent information - use only data returned by the search
- Wait for complete tool results before responding
- Provide detailed responses based on search results
- Always return links/URLs in markdown format when possible
"""
)

memory = MemorySaver()
root_agent = create_react_agent(llm, tools, prompt=system_message, checkpointer=memory)

AGENT_NAME = "web_search_agent"
AGENT_DESCRIPTION = "LangGraph agent with web search using Groq LLM"
```

### Weather Agent

Located in `langchain_agents/weather_agent/`:

```python
from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from environment import api_keys
from langchain_agents.weather_agent.tools import get_weather

llm = ChatGroq(model="llama3-70b-8192", api_key=api_keys.GROQ_API_KEY)

tools = [get_weather]

system_message = SystemMessage(
    content="""You are an intelligent assistant specialized in weather information.

MANDATORY INSTRUCTIONS:
- ALWAYS use the get_weather tool when users ask about weather in a city
- NEVER invent weather information - use only data returned by the tool
- Provide detailed and well-formatted responses based on weather query results
- Add useful comments about weather conditions when appropriate
"""
)

memory = MemorySaver()
root_agent = create_react_agent(llm, tools, prompt=system_message, checkpointer=memory)

AGENT_NAME = "weather_agent"
AGENT_DESCRIPTION = "LangGraph agent with weather information using Groq LLM"
```

## Tool Examples

### Web Search Tool

```python
from langchain.tools import tool
from pydantic import BaseModel, Field
from utilities.web_search import search

class WebSearchInput(BaseModel):
    """Input for performing a web search."""
    query: str = Field(description="Query to perform a web search.")

@tool("web_search", args_schema=WebSearchInput, return_direct=False)
def web_search(query: str) -> str:
    """Tool for performing web search on any topic.

    Use this tool ALWAYS when you need information about:
    - Specific people
    - Current events
    - Specific facts or data
    - Any information not in your knowledge base

    Args:
        query: Query to perform a web search.

    Returns:
        Formatted string with complete web search information.
    """
    try:
        result = search(query)
        return result
    except Exception as e:
        return f"Unexpected error performing web search: {str(e)}"
```

### Weather Tool with Enum Validation

```python
from enum import Enum
from typing import Literal
import requests
from langchain.tools import tool
from pydantic import BaseModel, Field

class CityEnum(str, Enum):
    """Available cities for weather consultation."""
    SAO_PAULO = "São Paulo"
    RIO_DE_JANEIRO = "Rio de Janeiro"
    BELO_HORIZONTE = "Belo Horizonte"
    # ... more cities

class GetWeatherInput(BaseModel):
    """Input for getting weather information."""
    city: Literal[
        "São Paulo",
        "Rio de Janeiro",
        "Belo Horizonte",
        # ... more cities
    ] = Field(description="City to get weather for. Choose from available options.")

@tool("get_weather", args_schema=GetWeatherInput, return_direct=False)
def get_weather(city: str) -> str:
    """Gets weather information for a specific city.

    Args:
        city: City name to query weather for

    Returns:
        Formatted string with complete weather information
    """
    # Implementation with API calls
    # ...
    return formatted_weather_result
```

## Agent Discovery and Registration

The system automatically:

1. **Scans** the `langchain_agents/` directory
2. **Discovers** subdirectories with `agent.py` files
3. **Imports** the `root_agent` from each file
4. **Registers** agents with ID `langchain-{directory_name}`
5. **Exposes** via REST API and OpenAI-compatible endpoints

## API Integration

Once configured, agents are available at:

- **Direct chat**: `POST /chat` with `model: "langchain-agent-name"`
- **OpenAI compatible**: `POST /v1/chat/completions` with `model: "langchain-agent-name"`
- **Model listing**: `GET /v1/models`

## Best Practices

### Agent Development

1. **Use LangGraph**: Always use `create_react_agent` from `langgraph.prebuilt`
2. **Memory Management**: Use `MemorySaver` for conversation state
3. **Clear Instructions**: Provide detailed system messages
4. **Tool Integration**: Use the `@tool` decorator for all tools
5. **Error Handling**: Implement proper error handling in tools

### Tool Development

1. **Input Validation**: Use Pydantic models for tool inputs
2. **Clear Descriptions**: Provide detailed tool and parameter descriptions
3. **Error Handling**: Handle exceptions gracefully
4. **Return Format**: Return formatted strings for better user experience
5. **Logging**: Add appropriate logging for debugging

### Code Organization

1. **Separate Files**: Keep each tool in its own file
2. **Proper Exports**: Use `__init__.py` to export tools
3. **Environment**: Use the Environment module for API keys
4. **Utilities**: Leverage existing utilities when possible

## Debugging and Testing

### Enable Verbose Logging

Add logging to your tools for debugging:

```python
@tool("my_tool", args_schema=MyToolInput, return_direct=False)
def my_tool(query: str) -> str:
    print(f"🚨 [TOOL] my_tool EXECUTING with query: '{query}'")
    try:
        result = perform_operation(query)
        print(f"✅ [TOOL] Operation completed successfully")
        return result
    except Exception as e:
        print(f"❌ [TOOL] ERROR: {str(e)}")
        return f"Error: {str(e)}"
```

### Test Tools Independently

```python
from langchain_agents.your_agent.tools import your_tool

# Test the tool directly
result = your_tool.invoke({"query": "test input"})
print(result)
```

### Test Agents Directly

```python
from langchain_agents.your_agent.agent import root_agent

# Test the agent
config = {"configurable": {"thread_id": "test"}}
response = root_agent.invoke(
    {"messages": [("user", "Hello, how can you help me?")]},
    config=config
)
print(response)
```

## Migration from Old LangChain

If you have old LangChain agents using `initialize_agent`, here's how to migrate:

### Old Structure (Deprecated)

```python
from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationBufferWindowMemory

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    memory=memory,
    verbose=True
)
```

### New Structure (LangGraph)

```python
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

system_message = SystemMessage(content="Your instructions here")
memory = MemorySaver()

root_agent = create_react_agent(
    llm,
    tools,
    prompt=system_message,
    checkpointer=memory
)
```

## Advanced Features

### Custom State Management

For more complex state management, you can create custom graphs:

```python
from langgraph.graph import StateGraph
from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    custom_field: str

# Define custom graph logic
# ... (advanced usage)
```

### Tool Calling Control

Control when tools should return results directly:

```python
@tool("direct_tool", return_direct=True)  # Results returned directly to user
def direct_tool(query: str) -> str:
    return "Direct result to user"

@tool("processing_tool", return_direct=False)  # Results processed by agent
def processing_tool(query: str) -> str:
    return "Result for agent to process"
```

This updated documentation reflects the modern LangGraph-based approach used in your current agents, with practical examples and best practices for development.
