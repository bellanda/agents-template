# Agents Template

A comprehensive template for building AI agent applications with pre-configured tools for interacting with Oracle databases, email services, SMB file sharing, and more. Now includes LibreChat integration and Google ADK support.

## Features

- Pre-configured agent setup for various use cases
- Integration with Google AI (Gemini) using Google ADK
- LibreChat compatibility with OpenAI-compatible endpoints
- Oracle database connectivity
- Email functionality for reports and alerts
- SMB file server access
- FastAPI server for exposing agents as API endpoints
- Jupyter notebooks for experimentation
- SQL utilities and scripts

## Project Structure

```
agents-template/
├── main.py              # FastAPI application with LibreChat integration
├── google_agents/       # Agent implementations
│   ├── test_agent/      # Example test agent
│   └── weather_agent/   # Example weather agent
├── utilities/           # Utility functions
│   ├── agents/         # Agent utilities
│   ├── database/       # Database utilities
│   ├── email/          # Email utilities
│   ├── excel/          # Excel utilities
│   └── server/         # Server utilities
├── constants/           # Configuration constants
│   ├── api_keys.py     # API key configurations
│   └── paths.py        # Path configurations
├── docs/               # Documentation
├── sql/                # SQL scripts and utilities
├── notebooks/          # Jupyter notebooks for experimentation
├── scripts/            # Utility scripts
├── .env                # Environment variables (not in version control)
├── pyproject.toml      # Project dependencies
└── ruff.toml           # Code formatting configuration
```

## Prerequisites

- Python 3.11 or later
- Oracle Instant Client (for Oracle database connections)
- Google AI API keys

## Installation

### Linux/macOS

```bash
# Clone the repository (or use as template)
cd YOUR_PROJECT_FOLDER

# Install uv (package manager)
curl -LsSf https://astral.sh/uv/install.sh | bash

# Install dependencies
uv sync
```

### Windows

```powershell
# Clone the repository (or use as template)
cd YOUR_PROJECT_FOLDER

# Install uv (package manager)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install dependencies
uv sync
```

## Configuration

1. Create a `.env` file in the root directory
2. Add your API keys and configuration variables:

```bash
# Example .env configuration
GOOGLE_API_KEY=your_google_api_key_here
# Add other environment variables as needed
```

## Running the Application

You can run the application in multiple ways:

### 1. Using the main FastAPI server (Recommended)

```bash
uv run main.py
```

This will start the FastAPI server on http://0.0.0.0:8000 with:

- LibreChat compatible endpoints
- OpenAI-compatible API at `/v1/chat/completions`
- Agent discovery and management
- Health check endpoints

### 2. Using the Google ADK tool

For web interface:

```bash
cd google_agents
uv run adk web
```

For API server:

```bash
cd google_agents
uv run adk api_server
```

## Available Endpoints

### Main API Endpoints

- `GET /` - Root endpoint with available models
- `GET /health` - Health check
- `POST /chat` - Direct chat with agents
- `POST /v1/chat/completions` - OpenAI-compatible endpoint for LibreChat
- `GET /v1/models` - List available agent models
- `POST /admin/reload-agents` - Reload agents dynamically

### LibreChat Integration

The application provides OpenAI-compatible endpoints that work seamlessly with LibreChat:

- Automatic agent discovery
- Streaming responses
- Session management
- Model selection

## Adding New Agents

To add a new agent:

1. Create a new directory in `google_agents/` with your agent name
2. Create an `agent.py` file with a `root_agent` variable definition
3. Create an `__init__.py` file that imports the agent from `agent.py`
4. Add any agent-specific tools in separate files
5. The agent will be automatically discovered on server restart

Example agent structure:

```
google_agents/
└── my_new_agent/
    ├── __init__.py
    ├── agent.py        # Contains root_agent variable
    └── tools.py        # Agent-specific tools (optional)
```

## Development

### Notebooks

Use the Jupyter notebooks in the `notebooks/` directory for experimentation and development:

```bash
uv run jupyter lab notebooks/
```

### SQL Development

SQL scripts and utilities are available in the `sql/` directory for database-related development.

### Scripts

Utility scripts are located in the `scripts/` directory for various automation tasks.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
