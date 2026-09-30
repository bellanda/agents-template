# Multi-Agent FastAPI Template

> Plug-in agents infrastructure for FastAPI + PostgreSQL projects.
> Self-contained. Drop it into any backend. Streaming-first. Vercel AI SDK compatible.

---

## What this is

A modular agents layer that you can run standalone or drop into an existing FastAPI project.

**This template is the CANONICAL AI layer for every app** (kailos, balizap, nexarena, optimuslar,
akmeo — user decision 2026-09-30). Improvements are made here first and propagated with
`backend/scripts/sync_agents_to_another_fastapi_project.py`. Fixed stack (rule
`.claude/rules/ai-agents.md`): OpenRouter **GLM 5.3 Flash** for text/image/video, Groq **Whisper**
for audio — nothing else. Full spec for agents: [`AGENTS_SUBSYSTEM.md`](AGENTS_SUBSYSTEM.md).

**Backend:** FastAPI + LangGraph + LangChain + asyncpg (PostgreSQL) + Granian
**Frontend:** React 19 + TanStack Router + Vercel AI SDK + Shadcn/ui

Covers:

- Auto-discovered agents with persistent conversation history (PostgreSQL)
- LangGraph checkpointing for stateful multi-turn agents
- Streaming via Vercel AI SDK Data Stream Protocol (reasoning + text)
- File processing: images (multimodal base64) + documents (MarkItDown → markdown)
- OpenAI-compatible (wire format only) `/chat/completions` endpoint
- React chat UI with model selector, reasoning display, attachments, and thread management
- One-shot helpers: `complete()` / `complete_structured()` with limiter, retry and real cost (`core/agents/llm.py`)
- Subagent delegation (`core/agents/subagents.py`, example `agents/research_supervisor_agent`)
- Media → text: Whisper audio, GLM image/video, multi-image calls (`media.py`), scanned-PDF OCR (`ocr.py`)
- Cost per call in `agent_message_usage` (real upstream cost when OpenRouter reports it), per-tenant monthly totals
- Tenant agent instructions: versioned Markdown per tenant+agent, built in ChatGPT, appended at runtime (`/agent-config` screen)
- Tool results rendered as cards via a `{type, data}` envelope (`tool_envelope.py`)

---

## Quick Start (standalone)

Config = `config/app/{local,staging,prod}.yaml` (non-secret, versioned) + `.env` (secrets + `ENVIRONMENT`).
See [Configuration layout](#configuration-layout).

```bash
cp .env.example .env         # set POSTGRES_PASSWORD, DATABASE_URL, OPENROUTER_API_KEY, GROQ_API_KEY
cd backend
uv sync
dbmate --env-file ../.env up   # dbmate only auto-reads ./.env; DATABASE_URL lives in the root .env
uv run src/api/main.py       # host-only dev; Settings resolves config/app/local.yaml
```

Frontend (Vite dev server proxies `/api` to `localhost:8000`):

```bash
cd frontend
bun install
bun dev
```

Full stack in Docker (postgres + dbmate + backend + nginx on `127.0.0.1:19080`):

```bash
docker compose up -d --build
```

---

## Project Structure

```
compose.yaml                   # include: config/docker/compose.${ENVIRONMENT}.yaml + ingress.${INGRESS_MODE}.yaml
check.sh                       # ruff + (pytest if any) + prettier + vitest + tsc/vite build
config/
├── app/{local,staging,prod}.yaml   # non-secret config (Settings source of truth)
├── docker/                    # compose.<env>.yaml (sizing, VITE_* build args), ingress.{loopback,gateway}.yaml
└── nginx/                     # conf.d/ (upstream, server blocks) + snippets/ (CSP, SSE proxy, SPA cache)
backend/
├── agents/                    # Agent definitions — auto-discovered at startup
│   ├── weather_agent/         # example: agent with tools (the common case)
│   ├── web_search_agent/      # example: tools + scraping core
│   └── research_supervisor_agent/  # example: supervisor delegating to a subagent
│
├── config/                    # Shared config (importable as `config`)
│   ├── settings.py            # Pydantic Settings: yaml + .env secrets, fail-fast at import
│   ├── integrations.py        # shim: provider keys/endpoints flattened from settings
│   ├── api.py                 # API prefix, upload paths + limits
│   ├── database.py            # asyncpg pool + get_conn
│   ├── paths.py               # BASE_DIR
│   ├── tools.py               # getenv_or_raise_exception (.env boundary)
│   └── uploads.py             # canonical save_upload pipeline
├── tests/
│   ├── app.test.yaml          # hermetic yaml (conftest sets APP_YAML_PATH to it)
│   └── compose.yml            # ephemeral test Postgres on :5433 (used by check.sh)
│
└── src/api/                   # FastAPI app (importable as `api`)
    ├── main.py
    ├── core/agents/           # CANONICAL layer: models/catalog, providers, llm (one-shot),
    │                          # media, ocr, subagents, callbacks (cost), history window,
    │                          # tenant instructions, tool envelope, checkpointer
    ├── core/logging.py        # structlog stack (NDJSON prod / console dev)
    ├── core/exceptions.py     # BadRequestError etc (HTTPException subclasses)
    ├── middlewares/           # LoggingMiddleware (request_id + http_request line)
    ├── models/agents/         # Pydantic models: chat_history, usage, checkpoint, agent_config(+version)
    ├── schemas/agents/        # DTOs of /agents/{id}/config
    ├── models/uploads/        # UserUpload + upload_jsonb (user-owned uploads)
    ├── repositories/agents/   # Chat history, usage, agent config CRUD (asyncpg)
    ├── repositories/uploads/  # UserUploadRepository (asyncpg)
    ├── services/agents/       # Registry, streaming, executors, agent config
    ├── services/auth.py       # get_auth_context identity seam
    └── routes/                # agents/ (chat, models, threads, agent_config) + uploads.py

frontend/src/
├── components/
│   ├── ai-elements/           # Chat UI primitives (Conversation, Message, Reasoning, PromptInput…)
│   ├── chat/                  # ChatView, use-chat-session, tool-results registry, suggestions
│   ├── agent-config/          # Tenant instructions screen (InstructionsCard, MarkdownPreview, versions)
│   └── sidebar/               # Thread history sidebar
├── lib/
│   ├── api.ts                 # fetchAgents, fetchThreads, fetchThreadMessages
│   └── thread-messages-cache.ts
└── hooks/
    └── useUserId.ts           # Returns user ID — replace for auth integration
```

---

## Integrating into an Existing FastAPI Project

Your project must already use: asyncpg, dbmate (plain-SQL migrations), FastAPI, the same `config/` architecture.

### Step 1 — Run the sync script

```bash
cd /path/to/this/template/backend
uv run scripts/sync_agents_to_another_fastapi_project.py --target /path/to/your/backend
```

Copies the agents layers (overwrite — local edits in the target are lost; improve the template
first) into your project:

- `src/api/core/agents/`, `src/api/schemas/agents/`
- `src/api/models/agents/`
- `src/api/repositories/agents/`
- `src/api/services/agents/`
- `src/api/routes/agents/`

Plus shared infra the agents layers import (skip-if-exists, so a richer target keeps its own):

- `src/api/middlewares/` (LoggingMiddleware), `src/api/models/uploads/`, `src/api/repositories/uploads/`
- `src/api/core/logging.py`, `src/api/core/exceptions.py`, `src/api/services/auth.py`, `src/api/routes/uploads.py`, `config/uploads.py`
- `db/migrations/*.sql` (existing files preserved)

Pass `--examples` to also copy the example agents (skip-if-exists). Existing apps: review the
copied migrations before `dbmate up` (see the per-app convergence checklist, AGENTS_SUBSYSTEM.md §17).

Pass `--optional` to also copy `config/` stubs and `src/api/core/database.py` (skipped if they already exist).

### Step 2 — Add dependencies

In your `pyproject.toml`:

```toml
dependencies = [
    # ... your existing deps ...
    "langchain>=1.2.10",
    "langchain-community>=0.4.1",
    "langchain-core>=1.2.17",
    "langchain-openai>=1.1.10",           # ChatOpenRouter extends ChatOpenAI
    "curl-cffi>=0.15.0",                  # Groq Whisper call (media.py)
    "pyyaml>=6.0.3",                      # config/settings.py
    "langgraph>=1.0.10",
    "langgraph-checkpoint-postgres>=3.0.4",
    "markitdown[all]>=0.1.5",
    "structlog>=25.5.0",                  # core/logging.py
    "opencv-python-headless>=4.13.0.92",  # config/uploads.py (image→AVIF)
    "numpy>=2.2.0",                       # config/uploads.py
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
from api.routes.agents import agents_router

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

### Step 4 — Run dbmate migrations

The agents migration ships in `db/migrations/` (copied by the sync script).

```bash
dbmate up
```

Creates: `agent_message_usage`, `chat_history`, `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `user_uploads`.

### Step 5 — Config: yaml keys + `.env` secrets

The layers read only `settings` / `config.integrations` (never `os.getenv`). The sync script prints the
exact keys; in short, add to **all three** `config/app/*.yaml`:

```yaml
openrouter: # single chat gateway (text/image/video)
  api_base: https://openrouter.ai/api/v1
  site_url: ""
  app_title: ""
agents:
  stream_debug: false # true only in local
```

(plus the `logging:` and `postgres.pool:` sections `core/logging.py` / `config/database.py` read), the matching
sub-models/fields in `config/settings.py`, and **secrets only** in `.env`:

```env
OPENROUTER_API_KEY=   # single chat gateway
GROQ_API_KEY=         # audio transcription (Whisper) only
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
from api.core.agents.custom_providers import init_model
from api.core.agents.models import Models
from api.core.agents.schemas import AgentConfig

config = AgentConfig(
    name="My Agent",
    description="What it does and which provider it uses",
    system_prompt="You are...",
    model=init_model(Models.OpenRouter.GLM_5_3_FLASH),
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

Registry: `from api.core.agents.models import Models`. Instantiate with
`init_model(Models.OpenRouter.GLM_5_3_FLASH)` (`core/agents/custom_providers.py`).

| Access                                 | Provider   | Notes                                                                 |
| -------------------------------------- | ---------- | --------------------------------------------------------------------- |
| `Models.OpenRouter.GLM_5_3_FLASH`      | openrouter | reasoning; text + image + video; no inline PDF/audio; US upstreams pinned |
| `Models.Groq.WHISPER_LARGE_V3_TURBO`   | groq       | transcription; **not a chat model**                                   |

`WHISPER_LARGE_V3_TURBO` does not go through `init_model` (raises `ValueError`): it is a multipart POST in
`core/agents/media.py`, billed per **audio hour**, not per token — the zeroed price fields are deliberate.
**Every chat model in the registry needs a price**: without it cost reads zero silently and any spend cap stops working.

Add a model: add a `ModelConfig` under `Models.OpenRouter` in `models.py`. Add a provider only by explicit decision
(each provider is one more inference route to audit): implement `init_<provider>_model()` in `custom_providers.py`
and add its key as a `SecretStr` in `Settings` + `.env.example`.

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

Identity is resolved by a single dependency, `get_auth_context`
(`src/api/services/auth.py`). Every agents/uploads route depends on it, so
swapping auth is a one-function change. By default it is **open**: identity comes
from `Authorization: Bearer <token>` → `X-User-Id` header → `user` query param →
`"default_user"`. `user_id` scopes thread history, usage accounting, and uploads.

**Backend**: replace `resolve_identity(token)` in `services/auth.py` with real
verification — decode the JWT, return `payload["sub"]`, raise
`AuthenticationError` on invalid tokens. No route changes needed.

**Frontend**: identity flows via the `X-User-Id` header on every agents/uploads
request (chat transport, `fetchThreads`, `uploadFile`, …). Replace the
`useUserId()` hook in `src/hooks/useUserId.ts` to return the real id; with a
token backend, send `Authorization: Bearer` instead. Signature must stay:

```typescript
function useUserId(): [string, () => void];
```

---

## Configuration layout

Same pattern as the product apps (kailos, balizap) — this template is the central base, so keep it in sync.

| What | Where | Notes |
| --- | --- | --- |
| Secrets + `ENVIRONMENT` + `INGRESS_MODE` | `.env` (root, gitignored; template in `.env.example`) | `POSTGRES_PASSWORD`, `DATABASE_URL`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `APP_UID`. **Only secrets + env selectors** |
| Non-secret config | `config/app/{local,staging,prod}.yaml` | `postgres.pool`, `logging`, `cors`, `openrouter`, `agents`, `vite`. Keep the 3 files symmetric |
| Runtime resolution | `backend/config/settings.py` | `APP_YAML_PATH` > `/app/app.yaml` (docker bind-mount of `config/app/${ENVIRONMENT}.yaml`) > `config/app/{ENVIRONMENT}.yaml` |
| Test config | `backend/tests/app.test.yaml` | conftest must set `APP_YAML_PATH` before importing `api`/`config` |
| Granian + resources | `config/docker/compose.<env>.yaml` | `GRANIAN_*` are compose env (read by the Dockerfile CMD), not yaml |
| `VITE_*` | yaml `vite:` (host) + `nginx.build.args` in `compose.<env>.yaml` (Docker build) | Must mirror each other; the image build cannot read the yaml |
| nginx | `config/nginx/` | `INGRESS_MODE=loopback` (dev, `127.0.0.1:19080`) or `gateway` (behind a central TLS gateway). No `edge` mode here — copy from kailos if an app needs it |

Rules: never the same key in yaml and `.env`; business code never calls `os.getenv`; new config = edit all
three yamls + a `Settings` sub-model; new secret = `.env.example` + a `SecretStr` field (skill `python-config-bootstrap`).
The host `.env` `DATABASE_URL` (localhost) is overridden inside docker by the compose `environment:` value.
