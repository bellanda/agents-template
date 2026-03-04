# Multi-Agent FastAPI Template

> Plug-in agents infrastructure for FastAPI + PostgreSQL projects.
> Self-contained. Drop it into any backend. Streaming-first. Vercel AI SDK compatible.

---

## What this is

A modular agents layer that you can run standalone or drop into an existing FastAPI project.

**Backend:** FastAPI + LangGraph + LangChain + asyncpg (PostgreSQL) + Granian
**Frontend:** React 19 + TanStack Router + Vercel AI SDK + Shadcn/ui

Covers:

- Auto-discovered agents with persistent conversation history (PostgreSQL)
- LangGraph checkpointing for stateful multi-turn agents
- Streaming via Vercel AI SDK Data Stream Protocol (reasoning + text)
- File processing: images (multimodal base64) + documents (MarkItDown → markdown)
- OpenAI-compatible `/chat/completions` endpoint
- React chat UI with model selector, reasoning display, attachments, and thread management

---

## Quick Start (standalone)

```bash
cd backend
cp ../.env.example ../.env   # fill in API keys + Postgres vars
uv sync
uv run alembic upgrade head
uv run src/api/main.py
```

Frontend:

```bash
cd frontend
bun install
bun dev
```

---

## Project Structure

```
backend/
├── agents/                    # Agent definitions — auto-discovered at startup
│   ├── web_search_agent/
│   │   ├── agent.py
│   │   └── tools/
│   └── weather_agent/
│       ├── agent.py
│       └── tools/
│
├── config/                    # Shared config (importable as `config`)
│   ├── api.py                 # Granian, upload limits, API prefix
│   ├── database.py            # asyncpg pool + get_conn
│   ├── paths.py               # BASE_DIR
│   └── tools.py               # getenv_or_raise_exception
│
└── src/api/                   # FastAPI app (importable as `api`)
    ├── main.py
    ├── core/agents/           # Model registry, checkpointer, schemas
    ├── models/agents/         # SQLAlchemy tables: checkpoints + chat_history
    ├── repositories/agents/   # Chat history CRUD (asyncpg)
    ├── services/agents/       # Registry, streaming, executors
    └── routes/agents/         # Endpoints: /chat/completions, /models, /threads

frontend/src/
├── components/
│   ├── ai-elements/           # Chat UI primitives (Conversation, Message, Reasoning, PromptInput…)
│   ├── ChatView.tsx           # Reference chat component
│   └── sidebar/               # Thread history sidebar
├── lib/
│   ├── api.ts                 # fetchAgents, fetchThreads, fetchThreadMessages
│   └── thread-messages-cache.ts
└── hooks/
    └── useUserId.ts           # Returns user ID — replace for auth integration
```

---

## Integrating into an Existing FastAPI Project

Your project must already use: asyncpg, SQLAlchemy + Alembic, FastAPI, the same `config/` architecture.

### Step 1 — Run the sync script

```bash
cd /path/to/this/template/backend
uv run scripts/sync_agents_to_another_fastapi_project.py --target /path/to/your/backend
```

Copies these directories into your project:

- `agents/`
- `src/api/core/agents/`
- `src/api/models/agents/`
- `src/api/repositories/agents/`
- `src/api/services/agents/`
- `src/api/routes/agents/`

Pass `--optional` to also copy `config/` stubs and `src/api/core/database.py` (skipped if they already exist).

### Step 2 — Add dependencies

In your `pyproject.toml`:

```toml
dependencies = [
    # ... your existing deps ...
    "langchain>=1.2.10",
    "langchain-cerebras>=0.8.2",
    "langchain-community>=0.4.1",
    "langchain-core>=1.2.17",
    "langchain-google-genai>=4.2.1",
    "langchain-groq>=1.1.2",
    "langchain-nvidia-ai-endpoints>=1.1.0",
    "langchain-openai>=1.1.10",
    "langgraph>=1.0.10",
    "langgraph-checkpoint-postgres>=3.0.4",
    "markitdown[all]>=0.1.5",
]

[tool.hatch.build.targets.wheel]
packages = ["config", "src/api", "agents"]    # add "agents"

[tool.hatch.build.targets.wheel.sources]
"agents" = "agents"                            # add this line
```

```bash
uv sync --upgrade
```

### Step 3 — Wire into main.py

```python
from api.core.agents.checkpointer import close_checkpointer, init_checkpointer
from api.services.agents.registry import reload_agents_registry
from api.routes.agents import router as agents_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_asyncpg_pool()
    await init_checkpointer()
    await reload_agents_registry()
    yield
    await close_checkpointer()
    await close_asyncpg_pool()

api_router.include_router(agents_router)
```

### Step 4 — Run Alembic migrations

```bash
uv run alembic revision --autogenerate -m "add agents tables"
uv run alembic upgrade head
```

Creates: `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `chat_history_threads`.

### Step 5 — Add .env variables

```env
# AI providers — add whichever your agents use
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=
NVIDIA_API_KEY=
CHUTES_API_KEY=
CEREBRAS_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
DEEPSEEK_API_KEY=
```

---

## Creating a New Agent

### 1. Create the directory

```
backend/agents/my_agent/
├── agent.py
└── tools/
    ├── __init__.py
    └── my_tool.py
```

### 2. Define the tool

```python
# agents/my_agent/tools/my_tool.py
from langchain_core.tools import tool


@tool
def my_tool(query: str) -> str:
    """What this tool does. The LLM reads this to decide when to call it."""
    return result
```

```python
# agents/my_agent/tools/__init__.py
from agents.my_agent.tools.my_tool import my_tool

__all__ = ["my_tool"]
```

### 3. Define the agent

```python
# agents/my_agent/agent.py
from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver

from agents.my_agent.tools import my_tool
from api.core.agents.models import models
from api.core.agents.schemas import AgentConfig

config = AgentConfig(
    name="My Agent",
    description="What it does and which provider it uses",
    system_prompt="You are...",
    model=models.Groq.KIMI_K2_INSTRUCT__GROQ,
    tools=[my_tool],
    suggestions=["Try asking me about...", "What is..."],
    save_to_db=True,   # False = stateless, no history
)


def create_root_agent(checkpointer: BaseCheckpointSaver | None = None):
    return create_agent(
        model=config.model,
        tools=config.tools,
        system_prompt=config.system_prompt,
        checkpointer=checkpointer,
    )
```

The directory name `my_agent` becomes the model ID `"my-agent"` (underscores → hyphens).
Restart the server — the agent is auto-discovered and registered.

---

## Available Models

Models are lazy-loaded. Import: `from api.core.agents.models import models`

| Access                                         | Provider | Notes     |
| ---------------------------------------------- | -------- | --------- |
| `models.Cerebras.GPT_OSS_120B__CEREBRAS`       | Cerebras |           |
| `models.Cerebras.QWEN_3_235B_A22B__CEREBRAS`   | Cerebras |           |
| `models.Chutes.GPT_OSS_120B_TEE__CHUTES`       | Chutes   | reasoning |
| `models.Chutes.MINIMAX_M2_5_TEE__CHUTES`       | Chutes   | reasoning |
| `models.Chutes.DEEPSEEK_V3_2_TEE__CHUTES`      | Chutes   | reasoning |
| `models.Chutes.KIMI_K2_5_TEE__CHUTES`          | Chutes   | reasoning |
| `models.Google.GEMINI_3_1_PRO_PREVIEW__GOOGLE` | Google   |           |
| `models.Google.GEMINI_3_FLASH_PREVIEW__GOOGLE` | Google   |           |
| `models.Groq.GPT_OSS_120B__GROQ`               | Groq     |           |
| `models.Groq.KIMI_K2_INSTRUCT__GROQ`           | Groq     |           |
| `models.NVIDIA.MINIMAX_M2_1__NVIDIA`           | NVIDIA   | thinking  |
| `models.NVIDIA.DEEPSEEK_V3_2__NVIDIA`          | NVIDIA   | thinking  |
| `models.NVIDIA.KIMI_K2_5__NVIDIA`              | NVIDIA   | thinking  |
| `models.NVIDIA.GPT_OSS_120B__NVIDIA`           | NVIDIA   | thinking  |

Add a new provider: implement `init_<provider>_model()` in `src/api/core/agents/custom_providers.py`, then add a container class in `models.py`.

---

## API Reference

Base URL: `/api/v1/agents`

| Method   | Path                   | Description                                      |
| -------- | ---------------------- | ------------------------------------------------ |
| `GET`    | `/`                    | List available agents (OpenAI model list format) |
| `POST`   | `/chat/completions`    | Chat endpoint — streaming and non-streaming      |
| `GET`    | `/threads`             | List threads (`?agent_id=`, `?user_id=`)         |
| `GET`    | `/threads/{thread_id}` | Get message history                              |
| `DELETE` | `/threads/{thread_id}` | Delete a thread                                  |

### POST /chat/completions

```json
{
  "model": "web-search-agent",
  "messages": [{ "role": "user", "content": "What are the latest AI news?" }],
  "stream": true,
  "session_id": "session_abc123",
  "user": "user_42",
  "files": ["/path/to/file.pdf"]
}
```

`files` supports local paths. Images are multimodal (base64). Documents are converted to markdown via MarkItDown.

---

## Streaming Protocol

The endpoint emits Vercel AI SDK Data Stream Protocol (`text/event-stream`):

```
data: {"type": "start", "messageId": "..."}
data: {"type": "reasoning-start", "id": "..."}
data: {"type": "reasoning-delta", "id": "...", "delta": "..."}
data: {"type": "reasoning-end", "id": "..."}
data: {"type": "text-start", "id": "..."}
data: {"type": "text-delta", "id": "...", "delta": "..."}
data: {"type": "text-end", "id": "..."}
data: {"type": "finish"}
data: [DONE]
```

The frontend uses `useChat` from `@ai-sdk/react` with `DefaultChatTransport`. No custom parsing needed — the SDK decodes parts automatically into `UIMessage.parts[]` with types `"reasoning"` and `"text"`.

---

## User Authentication

By default, all requests use `user = "default_user"`.

**Backend**: the `user` field in `ChatRequest` scopes thread history. Pass it from your auth system — no backend changes needed.

**Frontend**: replace the `useUserId()` hook in `src/hooks/useUserId.ts`. Signature must stay:

```typescript
function useUserId(): [string, () => void];
```

---

## Environment Variables

```env
# Server
HOST=0.0.0.0
PORT=8000
GRANIAN_INTERFACE=asgi
GRANIAN_HTTP=auto
GRANIAN_LOOP=uvloop
GRANIAN_WORKERS=4

# PostgreSQL
POSTGRES_DB=agents_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_POOL_MIN_SIZE=2
POSTGRES_POOL_MAX_SIZE=10
POSTGRES_POOL_MAX_QUERIES=50000
POSTGRES_POOL_MAX_INACTIVE_CONNECTION_LIFETIME=300
POSTGRES_POOL_COMMAND_TIMEOUT=60
POSTGRES_POOL_TIMEOUT=30

# AI Providers (add whichever you need)
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=
NVIDIA_API_KEY=
CHUTES_API_KEY=
CEREBRAS_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
DEEPSEEK_API_KEY=
```
