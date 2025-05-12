# Agents Template

A comprehensive template for building AI agent applications with pre-configured tools for interacting with Oracle databases, email services, SMB file sharing, and more.

## Features

- Pre-configured agent setup for various use cases
- Integration with Google AI (Gemini), OpenAI and Ollama locally
- Oracle database connectivity
- Email functionality for reports and alerts
- SMB file server access
- FastAPI server for exposing agents as API endpoints

## Project Structure

```
agents-template/
├── apis/                # API endpoints
│   └── main.py         # FastAPI application
├── constants/           # Configuration constants
├── data/                # Data files
│   └── server/         # Files served by the API
├── google_agents/       # Agent implementations
│   └── database_query_agent/  # Example agent
│       ├── agent.py    # Agent definition with root_agent variable
│       ├── __init__.py # Imports agent from agent.py
│       └── database.py # Tools specific to this agent
├── utilities/           # Utility functions
│   └── agents/         # Agent utilities
│       └── google/     # Utilities for Google AI agents
├── .env                 # Environment variables (not in version control)
├── .env.example         # Example environment variables
└── pyproject.toml       # Project dependencies
```

## Prerequisites

- Python 3.11 or later
- Oracle Instant Client (for Oracle database connections)
- Google AI and/or OpenAI API keys

## Installation

### Linux/macOS

```bash
# Clone the repository (or use as template)
cd YOUR_PROJECT_FOLDER

# Install uv (package manager)
curl -LsSf https://astral.sh/uv/install.sh | bash

# Install dependencies
uv sync

# Create directory structure (Git doesn't track empty directories)
mkdir -p data/server
```

### Windows

```powershell
# Clone the repository (or use as template)
cd YOUR_PROJECT_FOLDER

# Install uv (package manager)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install dependencies
uv sync

# Create directory structure (Git doesn't track empty directories)
mkdir -Force -Path data/server
```

## Configuration

1. Copy `.env.example` to `.env`
2. Update the values in `.env` with your credentials and API keys

```bash
cp .env.example .env
```

## Running the Application

You can run the application in two ways:

### 1. Using the ADK tool

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

### 2. Running the FastAPI server directly

```bash
uv run apis/main.py
```

This will start the FastAPI server on http://0.0.0.0:8005.

## Available Endpoints

- `GET /database_query_agent?instructions=your_instructions` - Executes database query agent with provided instructions
- `GET /download_file?file_name=your_file` - Downloads a file from the server's data directory

## Adding New Agents

To add a new agent:

1. Create a new directory in `google_agents/` with your agent name
2. Create an `agent.py` file with a `root_agent` variable definition
3. Create an `__init__.py` file that imports the agent from `agent.py`
4. Add any agent-specific tools in separate files
5. Add the agent configuration to `constants/api.py`
6. Create a new endpoint in `apis/main.py`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
