# 🧠 Multi-Agent API Template

> **Minimalist. High-Performance. Vercel AI SDK Compatible.**

🚀 **Ready-to-use** FastAPI template for deploying LangChain/LangGraph agents with streaming support, file processing (MarkItDown), and rich UI feedback.

---

## 🛠️ Quick Start

1.  **Install dependencies:**
    ```bash
    uv sync
    ```

2.  **Configure Environment:**
    ```bash
    cp .env.example .env
    # Fill in your API keys (OPENAI_API_KEY, etc.)
    ```

3.  **Run the Server:**
    ```bash
    uv run main.py
    ```

---

## 📦 Syncing to Another Project

Want to add these agents to an existing FastAPI project? We made it easy.

### 1. Run the Sync Script
This script copies the minimalist agent structure to your target backend.

```bash
uv run scripts/sync_agents_to_another_fastapi_project.py \
  --api-path ../my-app/backend/src/api \
  --backend-path ../my-app/backend
```

### 2. Configure the Target Project
After syncing, follow these steps in your **destination project**:

1.  **Environment Variables**:
    - Copy the contents of `.env.example` from this template to your target's `.env`.
    - Ensure you have valid API keys.

2.  **Verify Paths**:
    - Check that `backend/config/paths.py` exists and defines `BASE_DIR` using `pathlib`.
    - Confirm that `backend/config/api_keys.py` is present.

3.  **Update Dependencies**:
    - Open the `pyproject.toml` in your target project.
    - Copy the dependencies from this template's `pyproject.toml` into your target's file.
    - Run the included upgrade script to clean, sort, and install everything:
      ```bash
      uv run scripts/uv_upgrade_pyproject_dependencies.py
      ```

4.  **Register Routes**:
    - In your main application entry point (e.g., `main.py`), import and include the agents router:
      ```python
      from fastapi import FastAPI
      # Adjust import path based on your structure
      from api.routes.agents import router as agents_router

      app = FastAPI()

      # ... other routers ...
      app.include_router(agents_router, prefix="/api/v1", tags=["agents"])
      ```

---

## 📘 API Documentation

### Base URL
`/api/v1/agents` (depending on your prefix configuration)

### Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/models` | List available agents (OpenAI format, includes suggestions). |
| `POST` | `/chat/completions` | Main chat endpoint (Sync & Streaming). |
| `GET` | `/threads` | List conversation threads (supports `?agent_id=` and `?user_id=` filters). |
| `GET` | `/threads/{thread_id}` | Get message history for a specific thread. |
| `DELETE` | `/threads/{thread_id}` | Delete a conversation thread. |

### 👤 User Persistence

The template supports user-scoped conversation history. By default, it uses a mock user ID stored in `localStorage` (frontend) and filters threads by `user_id` in the backend.

**Frontend:** Uses `useUserId()` hook that returns `"default_user"` by default. The hook is designed to be easily replaced with your auth system - just update `src/hooks/useUserId.ts`.

**Backend:** The `user` field in `ChatRequest` is used to filter threads. If not provided, defaults to `"default_user"`. User ID is stored in checkpoint metadata for filtering.

**To implement real authentication:**
1. Replace `useUserId()` hook implementation in `src/hooks/useUserId.ts` with your auth provider
2. The hook signature `(): [string, () => void]` should remain the same
3. Backend will automatically filter threads by user ID

### 💡 Agent Suggestions

Agents can define suggested prompts via `AGENT_SUGGESTIONS` in their `agent.py`:

```python
AGENT_SUGGESTIONS = [
    "What are the latest trends in AI?",
    "How does machine learning work?",
    "Explain quantum computing",
]
```

These suggestions appear in the chat UI when no messages are present, allowing users to quickly start conversations.

### 🌊 Streaming & Rich UI Feedback

To support animations like "Thinking...", "Searching...", we inject **XML Status Tags** into the stream.

**Status Tag Format:**
```xml
<agent:status type="TYPE" name="NAME">CONTENT</agent:status>
```

**Frontend Parsing (React/JS Example):**
```javascript
const STATUS_REGEX = /<agent:status type="([^"]+)"(?: name="([^"]+)")?>(.*?)<\/agent:status>/g;

function parseChunk(text) {
  let cleanText = text;
  let matches = [];
  let match;

  while ((match = STATUS_REGEX.exec(text)) !== null) {
    matches.push({
      type: match[1],   // e.g., 'tool_start', 'thinking'
      name: match[2],   // e.g., 'Google Search'
      content: match[3] // e.g., 'querying docs...'
    });
  }

  cleanText = text.replace(STATUS_REGEX, '');
  return { cleanText, updates: matches };
}
```

### 📂 File Handling (MarkItDown)

Send files to be processed and added to the context automatically.

**JSON Payload:**
```json
{
  "model": "web-search-agent",
  "messages": [{ "role": "user", "content": "Analyze this file" }],
  "files": ["/local/path/to/file.pdf"],
  "stream": true
}
```

**Example (Excel/PDF/Text):**
```bash
curl -X POST http://localhost:8000/api/v1/agents/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "web-search-agent",
    "messages": [{ "role": "user", "content": "Qual foi o meu total restante em Julho de 2024?" }],
    "files": ["/home/bellanda/code/github-templates/agents-template/Despesas Mensais.xlsx"],
    "stream": false
  }'
```

**Example (Multimodal Image):**
```bash
curl -X POST http://localhost:8000/api/v1/agents/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "web-search-agent",
    "messages": [{ "role": "user", "content": "Describe this image" }],
    "files": ["/home/bellanda/downloads/chart.png"],
    "stream": false
  }'
```
