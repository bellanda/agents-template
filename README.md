# Agents Template

A comprehensive template for building AI agent applications with support for multiple agent frameworks, pre-configured tools, and OpenAI-compatible API endpoints. Features both Google ADK and LangChain agent implementations with automatic discovery and deployment.

## Features

- **Multi-Framework Agent Support**: Google ADK and LangChain agents
- **Automatic Agent Discovery**: Agents are automatically discovered and registered
- **OpenAI-Compatible API**: Full compatibility with LibreChat and other OpenAI-compatible clients
- **FastAPI Server**: High-performance API server with streaming responses
- **Pre-configured Utilities**: Database, email, file operations, and Excel utilities
- **Development Tools**: Jupyter notebooks, SQL utilities, and development scripts
- **Modern Python Stack**: Built with uv package manager and modern Python practices

## Project Structure

```
agents-template/
├── main.py                    # FastAPI application with OpenAI-compatible endpoints
├── google_agents/             # Google ADK agent implementations
│   └── weather_agent/         # Example Google weather agent
├── langchain_agents/          # LangChain agent implementations
│   ├── web_search_agent/      # Example web search agent
│   └── weather_agent/         # Example LangChain weather agent
├── llms/                      # LLM provider configurations
│   ├── groq.py               # Groq API configuration
│   └── nvidia.py             # NVIDIA API configuration
├── utilities/                 # Utility functions and helpers
│   ├── database/             # Database connection utilities
│   ├── email/                # Email functionality
│   ├── excel/                # Excel operations
│   ├── server/               # Server utilities
│   └── web_search/           # Web search utilities
├── constants/                 # Configuration constants
│   ├── api_keys.py           # API key configurations
│   └── paths.py              # Path configurations
├── data/                     # Data files and datasets
├── docs/                     # Documentation
├── notebooks/                # Jupyter notebooks for experimentation
├── scripts/                  # Utility and automation scripts
├── sql/                      # SQL scripts and database utilities
├── pyproject.toml            # Project dependencies and configuration
├── uv.lock                   # Dependency lock file
└── ruff.toml                 # Code formatting and linting configuration
```

## Prerequisites

- Python 3.11 or later
- uv package manager
- API keys for your chosen LLM providers (Google AI, OpenAI, Groq, NVIDIA, etc.)

## Installation

### Linux/macOS

```bash
# Clone the repository (or use as template)
cd YOUR_PROJECT_FOLDER

# Install uv (package manager)
curl -LsSf https://astral.sh/uv/install.sh | bash

# Install dependencies
uv sync

# Create environment file
cp .env.example .env  # Edit with your API keys
```

### Windows

```powershell
# Clone the repository (or use as template)
cd YOUR_PROJECT_FOLDER

# Install uv (package manager)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install dependencies
uv sync

# Create environment file
copy .env.example .env  # Edit with your API keys
```

## Configuration

1. Create a `.env` file in the root directory
2. Add your API keys and configuration variables:

```bash
# Example .env configuration
GOOGLE_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
GROQ_API_KEY=your_groq_api_key_here
NVIDIA_API_KEY=your_nvidia_api_key_here

# Database configuration (if using Oracle)
ORACLE_HOST=your_oracle_host
ORACLE_PORT=1521
ORACLE_SERVICE=your_service_name
ORACLE_USER=your_username
ORACLE_PASSWORD=your_password

# Email configuration (if using email features)
SMTP_HOST=your_smtp_host
SMTP_PORT=587
SMTP_USER=your_email
SMTP_PASSWORD=your_password
```

## Running the Application

### Main FastAPI Server (Recommended)

```bash
uv run main.py
```

This starts the FastAPI server on http://0.0.0.0:8000 with:

- **OpenAI-Compatible Endpoints**: Full compatibility with LibreChat and other clients
- **Automatic Agent Discovery**: All agents are automatically discovered and registered
- **Streaming Responses**: Real-time streaming for better user experience
- **Session Management**: Built-in session handling for conversations
- **Health Monitoring**: Health check endpoints for monitoring

### Google ADK Tools (Alternative)

For Google ADK web interface:

```bash
cd google_agents
uv run adk web
```

For Google ADK API server:

```bash
cd google_agents
uv run adk api_server
```

## API Endpoints

### Core Endpoints

- `GET /` - Root endpoint with available models and system information
- `GET /health` - Health check endpoint
- `POST /chat` - Direct chat interface with agents
- `POST /v1/chat/completions` - OpenAI-compatible chat completions endpoint
- `GET /v1/models` - List all available agent models
- `POST /admin/reload-agents` - Dynamically reload agents without restart

### OpenAI Compatibility

The application provides full OpenAI API compatibility:

- **Chat Completions**: Standard `/v1/chat/completions` endpoint
- **Model Listing**: `/v1/models` endpoint with all available agents
- **Streaming Support**: Real-time response streaming
- **Message History**: Conversation context management
- **Error Handling**: Standard OpenAI error response format

## Agent Development

### Adding Google ADK Agents

1. Create a new directory in `google_agents/` with your agent name
2. Create an `agent.py` file with a `root_agent` variable
3. Create an `__init__.py` file that imports the agent
4. Add tools in a `tools/` subdirectory (optional)
5. The agent will be automatically discovered as `google-{agent_name}`

Example structure:

```
google_agents/
└── my_agent/
    ├── __init__.py
    ├── agent.py        # Contains root_agent variable
    └── tools/          # Optional tools directory
        ├── __init__.py
        └── my_tool.py
```

### Adding LangChain Agents

1. Create a new directory in `langchain_agents/` with your agent name
2. Create an `agent.py` file with a `root_agent` variable
3. Add tools in a `tools/` subdirectory (optional)
4. The agent will be automatically discovered as `langchain-{agent_name}`

Example structure:

```
langchain_agents/
└── my_agent/
    ├── agent.py        # Contains root_agent variable
    └── tools/          # Optional tools directory
        ├── __init__.py
        └── my_tool.py
```

### Agent Requirements

Each agent must:

- Export a `root_agent` variable in `agent.py`
- Have `name` and `description` attributes
- Be compatible with their respective framework (Google ADK or LangChain)

## Development

### Jupyter Notebooks

Use notebooks for experimentation and development:

```bash
uv run jupyter lab notebooks/
```

### Database Development

SQL scripts and utilities are available in the `sql/` directory:

```bash
# Example: Run SQL scripts
uv run python sql/your_script.py
```

### Utility Scripts

Automation and utility scripts in the `scripts/` directory:

```bash
# Example: Run utility scripts
uv run python scripts/your_script.py
```

### Code Quality

The project uses Ruff for code formatting and linting:

```bash
# Format code
uv run ruff format

# Check linting
uv run ruff check
```

## Integration with LibreChat

This template is fully compatible with LibreChat:

1. Start the FastAPI server: `uv run main.py`
2. In LibreChat, add a custom endpoint:
   - **Base URL**: `http://localhost:8000/v1`
   - **API Key**: Any value (not validated in development)
   - **Model**: Choose from available agents (e.g., `google-weather-agent`, `langchain-web-search-agent`)

## Available Utilities

The `utilities/` directory provides:

- **Database**: Oracle database connections and query utilities
- **Email**: SMTP email sending with HTML templates
- **Excel**: Excel file generation with styling and templates
- **Web Search**: Web search functionality for agents
- **Server**: Server-related utilities and helpers

## Example Agents

The template includes example agents:

- **Google Weather Agent**: Weather information using Google ADK
- **LangChain Weather Agent**: Weather information using LangChain
- **LangChain Web Search Agent**: Web search capabilities using LangChain

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For questions and support:

1. Check the documentation in the `docs/` directory
2. Review example agents and utilities
3. Open an issue on GitHub for bugs or feature requests
