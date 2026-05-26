# Agents Subsystem — Canonical Spec

> **O que é este documento.** A especificação completa, tópico a tópico, do subsistema de
> agentes deste template (FastAPI + LangChain 1.x / LangGraph + asyncpg + dbmate). É a fonte
> de verdade do que o template **cria** e dos padrões que ele **força**. Pode ser enviado como
> prompt para um projeto novo recriar tudo de forma idêntica, ou usado como checklist de
> auditoria. Propaga via `backend/scripts/sync_agents_to_another_fastapi_project.py`.

---

## 0. Princípios de enforcement (LangChain 1.x / LangGraph)

O subsistema impõe **um único jeito** de fazer cada coisa — daí ficar limpo e os agentes ficarem
resumidos (só config + tools):

- **Modelos & provedores num registro único.** Todo modelo é um `ModelConfig` frozen em
  `core/agents/models.py` (`Models.<Provider>.<NAME>`). Provider, pricing e capabilities vivem
  ali — nunca espalhados. Instanciar só via `init_model(cfg)` / `init_model_by_id(id)`
  (`core/agents/custom_providers.py`). Um `match config.provider` é o único ponto que conhece SDKs.
- **Agente = `create_agent(...)` (LangChain 1.x).** Sem grafos manuais para o caso comum. Um agente
  é só: modelo + system prompt + tools + middleware + checkpointer.
- **Custo medido em todo `on_llm_end`.** Callback global, sem instrumentação manual por agente.
- **Persistência estruturada.** Checkpointer (LangGraph) para o estado do grafo; `chat_history`
  para o transcript renderizável; `agent_message_usage` para custo. Tabelas versionadas via dbmate.
- **Boundary de tipos.** Pydantic V2 nos contratos (`schemas.py`), `dict`/escalares nos repos.

---

## 1. O que o template cria (inventário de arquivos)

### `core/agents/` — infraestrutura (idêntica entre projetos)
| Arquivo | Responsabilidade |
| --- | --- |
| `models.py` | `ModelConfig` (provider, pricing, capabilities) + registro `Models` + `compute_cost_usd` + `find_model_config` / `find_model_config_by_id` + `model_capabilities_dict` + `PROVIDER_ALIASES`/`canonical_provider`. |
| `custom_providers.py` | `init_model(cfg)` / `init_model_by_id(id)` + `init_<provider>_model`. `ChatDeepSeekRoundtrip` (round-trip de `reasoning_content`). |
| `callbacks.py` | `UsageRecorderCallback` — persiste 1 linha em `agent_message_usage` por chamada de LLM. |
| `checkpointer.py` | `AsyncPostgresSaver` singleton (`init_checkpointer`/`get_checkpointer`/`close_checkpointer`). |
| `history_window.py` | `sliding_window_middleware` — corta o histórico enviado ao LLM por orçamento de tokens/mensagens. |
| `prompt_cache.py` | Placeholder in-memory (caching real é nativo do provedor). |
| `schemas.py` | `AgentConfig`, `AgentSuggestion`, `ChatRequest`, capability DTOs. |

### `src/api/{models,repositories,routes,services}/agents/`
| Arquivo | Responsabilidade |
| --- | --- |
| `models/agents/usage.py` | `AgentMessageUsage` (Pydantic, espelha `agent_message_usage`). |
| `models/agents/history.py` | `ChatHistoryThread` (espelha `chat_history`). |
| `models/agents/checkpoint_jsonb.py` | `AgentCheckpoint`/`AgentCheckpointWrite` (value-objects do langgraph; pulado pelo check_schema). |
| `repositories/agents/usage.py` | `build_usage_from_ai_message`, `insert_agent_message_usage`, `get_thread_total_cost_usd`, `get_user_total_cost_usd`. |
| `repositories/agents/chat_history.py` | `get_chat_messages`, `save_chat` (upsert), `get_user_threads`, `delete_chat`. |
| `routes/agents/chat.py` | `POST /agents/chat/completions` (stream e não-stream) + extração multimodal. |
| `routes/agents/threads.py` | `GET/DELETE /agents/threads`, `GET /agents/threads/{id}`. |
| `routes/agents/models.py` | `GET /agents` — lista agentes/modelos com `capabilities`. |
| `services/agents/registry.py` | `discover_agents()` — auto-discovery da pasta `agents/`. |
| `services/agents/executors.py` | `call_agent_async`/`execute_agent` (one-shot) + extração de reasoning. |
| `services/agents/streaming.py` | `stream_agent` — SSE + save destacado + tool/reasoning parts. |
| `services/agents/utils.py` | `convert_file_to_text` (MarkItDown). |

### Infra compartilhada (importada pelas camadas de agents; copiada skip-if-exists)
| Arquivo | Responsabilidade |
| --- | --- |
| `core/logging.py` | Stack structlog → stdlib → QueueHandler/QueueListener → stderr. `setup_logging`/`shutdown_logging`/`get_logger`/`bind_request_id`. JSON (orjson) em prod, console em dev. Config via env (`LOG_LEVEL`/`LOG_FORMAT`/`SERVICE_NAME`/`APP_ENV`). |
| `core/exceptions.py` | `BadRequestError`/`AuthenticationError`/`ForbiddenError`/`NotFoundError` — subclasses de `HTTPException` (FastAPI trata nativo, sem handler custom). |
| `middlewares/logging_middleware.py` | `LoggingMiddleware` (ASGI puro) — lê `X-Request-ID`, bind em contextvar, 1 linha `http_request` por request com método/path/status/duration_ms. |
| `services/auth.py` | `get_auth_context` — seam única de identidade (Bearer → `X-User-Id` → `user` query → `default_user`). Ver §4. |
| `models/uploads/upload_jsonb.py` | `UploadKind`/`UploadVisibility`/`UploadAcl`/`UploadMetadata` (enums + JSONB shapes). |
| `models/uploads/user_upload.py` | `UserUpload` (espelha `user_uploads`; `owner_user_id: str`). |
| `repositories/uploads/user_upload_repository.py` | `UserUploadRepository` (create/update/find/soft_delete/hard_delete/find_by_entity). |
| `routes/uploads.py` | `POST /uploads` — gate capability + quota + dedup SHA-256 + `save_upload` + row em `user_uploads` (ver §8). |
| `config/uploads.py` | `save_upload` canônico (raw/image-AVIF/document) + `org_dir`/`user_dir` + filename `{slug}-{uuid4}.{ext}`. Core idêntico entre projetos. |

### `agents/<name>/` — agentes de exemplo (o contrato)
`weather_agent/` e `web_search_agent/`: cada um expõe `config: AgentConfig` + `create_root_agent(checkpointer=None)` + `tools/`.

### `db/`
`db/migrations/<ts>_initial.sql` (dbmate) + `db/schema.sql`: cria `agent_message_usage`,
`chat_history`, `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `user_uploads` + função
`update_updated_at_column`.

---

## 2. Registro de modelos & esquema barato (DeepSeek / Groq)

`ModelConfig` (frozen dataclass) em `core/agents/models.py`:

```python
@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    provider: str                      # deepseek | groq | google | openai | nvidia | cerebras | chutes
    reasoning: bool = False            # emite reasoning_content no stream
    thinking: bool = False             # google include_thoughts / nvidia chat_template_kwargs
    reasoning_effort: str | None = None  # low | high | max  (DeepSeek/OpenAI)
    input_price_per_1m: float = 0.0
    cached_input_price_per_1m: float = 0.0
    output_price_per_1m: float = 0.0
    supports_image_input: bool = False
    supports_pdf_input: bool = False
    supports_audio_input: bool = False
    supports_video_input: bool = False
```

**Esquema barato recomendado (USD por 1M tokens):**

| Uso | Modelo | input / cached / output | Notas |
| --- | --- | --- | --- |
| Atendente texto (default) | `deepseek-v4-flash` | 0.14 / 0.0028 / 0.28 | `reasoning_effort="high"`. Melhor custo/qualidade. |
| Texto premium | `deepseek-v4-pro` | 0.435 / 0.003625 / 0.87 | quando precisa de mais capacidade. |
| Áudio → texto | Groq `whisper-large-v3-turbo` | barato | shim para modelos text-only (ver §8). |
| Imagem → texto | Groq `meta-llama/llama-4-scout-17b-16e-instruct` | barato | shim de visão para modelos text-only. |
| Multimodal nativo | `gemini-3-flash-preview` | 0.50 / 0.05 / 3.00 | aceita imagem/pdf/áudio inline. |

**Regra:** atendente padrão = DeepSeek V4 Flash text-only + shims Groq (Whisper/visão). Garante o
fluxo mais barato e funcional. Trocar de modelo = trocar 1 `ModelConfig` no agente; o resto (custo,
streaming, capabilities) acompanha automático.

---

## 3. Contrato do agente (limpo e resumido)

Cada `agents/<name>/agent.py` expõe:

```python
config = AgentConfig(
    name="...", description="...",
    system_prompt=SYSTEM_PROMPT,
    model=init_model(Models.DeepSeek.V4_FLASH),
    tools=[tool_a, tool_b],
    save_to_db=True,
    capabilities=model_capabilities_dict(Models.DeepSeek.V4_FLASH),
    suggestions=[...],
)

def create_root_agent(checkpointer=None):
    return create_agent(
        model=config.model,
        tools=config.tools,
        system_prompt=config.system_prompt,
        middleware=[sliding_window_middleware],
        checkpointer=checkpointer,   # injetado pelo registry
    )
```

- **Auto-discovery** (`registry.py`): varre `agents/`, importa `agents.<name>.agent`, lê `config` +
  `create_root_agent` (ou `root_agent` pré-construído), injeta o checkpointer compartilhado quando
  `save_to_db=True`, e anexa o `usage_recorder` global. Chave do registro = `model_id` (`_`→`-`).
- **Tools**: `@tool("name", args_schema=PydanticModel)` em `agents/<name>/tools/`. Docstring = o que o
  LLM lê. Sem boilerplate além disso.

---

## 4. Auth para chats

**Seam única `get_auth_context`** (`services/auth.py`). Toda rota de chat/threads/uploads depende
dela — trocar auth = trocar **uma função** (`resolve_identity`). Aberta por default (o template roda
standalone). Precedência de identidade (primeiro não-vazio vence):

1. `Authorization: Bearer <token>` → `resolve_identity(token)` (stub: o token **é** o `user_id`).
2. Header `X-User-Id`.
3. Query param `user`.
4. `DEFAULT_USER_ID` (`"default_user"`).

Retorna `{"user_id", "client_id", "roles"}`. `client_id` vem de `X-Client-Id`/`client_id`.

| Camada | Padrão no template | Como os apps reforçam |
| --- | --- | --- |
| Rotas de chat/threads/uploads | `ctx = Depends(get_auth_context)` → `user_id = ctx["user_id"]` (header/token, **nunca** o body). `threads` são owner-scoped (403 se outro dono). | Substituir `resolve_identity` por verificação JWT real (decode → `payload["sub"]`, raise `AuthenticationError`). |
| Rotas de gestão de config | n/a no template | kailos/balizap: `@permission_service.require_authentication()` + `require_permission_in_org("agent_config:read|manage")`, `user_id = request.state.auth_context["user_id"]`. |
| Webhook inbound (WhatsApp) | n/a no template | HMAC SHA-256 (`_verify_whatsapp_signature` + `WHATSAPP_APP_SECRET`); responde 200 ≤10s e processa via fila. |

`user_id`/`client_id` derivados da seam fluem para checkpointer config, `usage_recorder` metadata e
`chat_history`. **Frontend:** identidade vai no header `X-User-Id` em toda chamada (chat transport,
`fetchThreads`, `uploadFile`, …) — `useUserId()` é o ponto de troca no front.

---

## 5. Request único → Response **VS** Chat contínuo (thread)

Ambos no mesmo endpoint `POST /agents/chat/completions`, decididos por `stream` e `session_id`:

- **One-shot (stateless-ish)** — `stream=false` → `call_agent_async` → `execute_agent` →
  `agent.ainvoke(...)`. Retorna JSON OpenAI-like. Se `session_id` for reusado, o checkpointer ainda
  carrega o histórico (não é stateless puro — é "one request, thread opcional").
- **Chat contínuo (threaded)** — `stream=true` → `stream_agent` (SSE). `thread_id = session_id`
  (gerado se ausente) é passado em `config["configurable"]["thread_id"]`; o `AsyncPostgresSaver`
  carrega/salva o estado do grafo automaticamente a cada turno.
- **Recuperar threads:** `GET /agents/threads?user_id=`, `GET /agents/threads/{id}`,
  `DELETE /agents/threads/{id}` (lê/escreve `chat_history`).
- **WhatsApp (kailos/balizap):** sempre threaded, `thread_id = conversation.agent_thread_id || conversation.id` (uma thread por conversa).

---

## 6. Streaming (SSE — protocolo Vercel AI SDK v5)

`StreamingResponse(media_type="text/event-stream")` emitindo JSON por evento:

`start` → `text-start`/`text-delta`/`text-end` · `reasoning-start`/`reasoning-delta`/`reasoning-end`
· `tool-input-available` / `tool-output-available` / `tool-output-error` · `error` · `finish`.

- **Reasoning/thinking:** extraído de `content[]` (Gemini/OpenAI Responses) e de
  `additional_kwargs["reasoning_content"]` (DeepSeek/Chutes/Cerebras), reemitido como `reasoning-delta`.
- **DeepSeek thinking multi-turno:** `ChatDeepSeekRoundtrip` reinjeta o `reasoning_content` da
  AIMessage anterior — sem isso a API DeepSeek dá 400.

---

## 7. Contabilização de preço (input / cached / output)

- **Callback** `UsageRecorderCallback` (anexado globalmente no registry e via `config["callbacks"]`):
  em `on_chat_model_start` guarda metadata por `run_id`; em `on_llm_end` lê `usage_metadata` +
  `response_metadata`, resolve o `ModelConfig` (`find_model_config`) e insere em `agent_message_usage`.
- **Fórmula** (`compute_cost_usd`): `(fresh_input·in + cached·cached_in + output·out) / 1e6`, com
  `fresh_input = input_tokens - cache_read`, **arredondando para cima** (nunca sub-cobra).
- **Tabela `agent_message_usage`:** `thread_id, message_id, user_id, client_id, agent_id, provider,
  model_id, input_tokens, cached_input_tokens, output_tokens, reasoning_tokens, total_tokens,
  cost_usd, error, created_at`. Imutável (sem `updated_at`).
- **Agregações:** `get_thread_total_cost_usd`, `get_user_total_cost_usd`. O custo também é embutido no
  `chat_history` (campo `usage` da mensagem assistant) para exibição.
- Praticamente todos os provedores hoje retornam input/cached/output → o cálculo é confiável.

---

## 8. Uploads & multimodal (fallback por modelo)

Há **dois padrões** no ecossistema — escolha por modalidade:

### A. Chat playground (template / optimuslar) — MarkItDown + multimodal nativo
- `POST /uploads`: owner = `ctx["user_id"]` (sessão, nunca param do cliente). Valida **capability** do
  modelo (415 se `image/audio/video` e o modelo não suporta), **tamanho**
  (`IMAGE_MAX_BYTES`/`DOCUMENT_MAX_BYTES`), **whitelist MIME** (documentos), **quotas** (por
  thread/usuário) e **dedup** por SHA-256.
- **Persistência universal:** grava via `save_upload` (`config/uploads.py`) — imagem→AVIF por profile,
  documento com whitelist, filename `{slug}-{uuid4}.{ext}` em
  `users/{user_id}/chat/threads/{thread_id}/` — e cria a row em `user_uploads` (`kind=attachment`,
  `visibility=private`, `entity_type=chat_session`). Dedup por SHA-256 reaproveita o arquivo sem
  regravar nem duplicar row.
- Na montagem da mensagem (`_extract_user_content` em `routes/agents/chat.py`):
  - **imagem** → parte `image_url` inline (se o modelo tem `supports_image_input`; senão **400**).
  - **documento/áudio/vídeo** → **MarkItDown** extrai texto e injeta como texto.
- **Frontend** monta o `accept=` do file picker a partir de `capabilities` (documentos sempre aceitos
  porque viram texto; `image/audio/video` só se o modelo suportar). Validador client-side opcional:
  `useFileUpload` (validator-only); a mutation é `uploadFile` em `lib/api.ts` (erros como `UploadError`).
- **Limpeza:** `DELETE /agents/threads/{id}` faz soft-delete das rows `user_uploads` da thread +
  remove o diretório de uploads (`delete_directory`).

### B. WhatsApp (kailos/balizap) — shims de transcrição/visão para modelo text-only
- DeepSeek é text-only → mídia inbound vira texto **antes** do agente (`_row_to_text`):
  **áudio → Groq Whisper** (`transcription.py`), **imagem → Groq Llama-4 visão** (`vision.py`),
  ambos fail-soft (fallback para placeholder). Vídeo/documento → placeholder/link.

### Capability flags
`supports_image_input` é o único **enforçado** (gate 415/400). `supports_pdf/audio/video` são
**informacionais** para o frontend; no fluxo MarkItDown, todo não-imagem vira texto. Exposto em
`GET /agents` via `model_capabilities_dict`.

### Alinhamento com o padrão universal de uploads (`uploads.md`) ✓
O template está **alinhado**: `config/uploads.py` (core idêntico entre projetos) + tabela
`user_uploads` (migration + schema.sql) + `UserUpload`/`upload_jsonb` + `UserUploadRepository` +
`routes/uploads.py` persistindo. **Diferença de base:** o template é **user-owned** —
`user_uploads.owner_user_id` é `VARCHAR(255)` (a identidade do template é string; não há tabela
`users`). Projetos org-owned criam também `org_uploads` + `OrgUpload`/repo (ver `uploads.md`).
**Storage:** filesystem local hoje; `# TODO(b2)` em `config/uploads.py` marca a costura para object
storage (B2/S3/Azure/GCS) atrás de um `StorageBackend` Protocol — assinatura de `save_upload` não muda.

---

## 9. Interrupção: bloquear, salvar e persistir

- **Cancelamento de stream** (`streaming.py`): captura `asyncio.CancelledError`, adiciona marcador
  `_Interrompido pelo usuário._` e dispara um **save destacado** (`_spawn_detached`) que **sobrevive
  ao cancelamento** do request — grava o turno parcial em `chat_history` (upsert `ON CONFLICT`).
- **Checkpointer**: o estado do grafo (mensagens, tool calls, reasoning) é persistido pelo LangGraph a
  cada passo — recuperável mesmo se o cliente cair.
- **WhatsApp (kailos/balizap)**: interrupção/desligamento do agente → `transition(state="human_handling")`
  + `conversation_state_events.log(reason="ai_disabled")` + `handoff_summary` persistido como mensagem
  interna. Debounce/superseded via Valkey (`DebounceRetryError`/`TriggerSupersededError`) controla
  reprocessamento na fila.

---

## 10. History window & prompt cache

- **`sliding_window_middleware`** (`history_window.py`): mantém o turno atual intacto e, andando do mais
  recente ao mais antigo, substitui `ToolMessage` pesados por placeholder até o orçamento
  (`MAX_MESSAGES_TO_LLM=80`, `MAX_TOKENS_HEURISTIC=256k`, divisor 4). Remove `ToolMessage` órfão no
  início (quebra Gemini). O histórico completo continua no checkpoint para replay na UI.
- **`prompt_cache.py`**: placeholder; caching real é nativo do provedor (reportado em `cache_read` e
  cobrado por `cached_input_price_per_1m`).

---

## 11. Schema de banco (dbmate)

`db/migrations/<ts>_initial.sql` cria: `update_updated_at_column()`, `agent_message_usage`
(+índices client_id/created_at/thread_id), `chat_history` (+trigger updated_at, índices), as três
tabelas do langgraph `checkpoints`/`checkpoint_writes`/`checkpoint_blobs`, e `user_uploads`
(+CHECK `kind`/`visibility`, índices owner_user_id/entity/kind, trigger updated_at). **Schema
versionado via dbmate** (não `checkpointer.setup()` em runtime — sem DDL no startup). `db/schema.sql`
é o dump canônico, regenerado a cada `dbmate up`. `check_schema.py`: `UserUpload`→`user_uploads`,
`upload_jsonb.py` pulado (sufixo `_jsonb`).

---

## 12. Wiring (main.py / lifespan)

```python
from api.core.logging import get_logger, setup_logging, shutdown_logging
from api.middlewares.logging_middleware import LoggingMiddleware

setup_logging()                  # antes de criar o app
log = get_logger(__name__)

async def lifespan(app):
    await init_asyncpg_pool()
    await init_checkpointer()
    await reload_agents_registry()
    yield
    await close_checkpointer()
    await close_asyncpg_pool()
    shutdown_logging()

app.add_middleware(CORSMiddleware, ...)
app.add_middleware(LoggingMiddleware)          # 1 linha http_request por request
api_router.include_router(agents_router)
api_router.include_router(uploads_router, prefix="/uploads", tags=["Uploads"])
# Mount AFTER o api_router (POST /uploads vence, GETs caem no static):
app.mount(api_config.UPLOADS_HTTP_PREFIX, StaticFiles(directory=api_config.UPLOADS_DIR), name="uploads")
```

---

## 13. Logging (structlog)

Stack fixo (ver rule `logging.md`): structlog → stdlib `logging` → QueueHandler/QueueListener →
stderr. `JSONRenderer`(orjson, NDJSON) em prod, `ConsoleRenderer` em dev (TTY-aware). Config por env
(`LOG_LEVEL`/`LOG_FORMAT=auto|json|console`/`SERVICE_NAME`/`APP_ENV`) — o template **não** tem
`config/settings.py`, então `core/logging.py` lê de `os.getenv` com defaults seguros.

- **Uso:** `from api.core.logging import get_logger` → `log = get_logger(__name__)`.
- Evento = `snake_case`, contexto = kwargs (`log.info("stream_agent_start", session_id=..., model=...)`).
  Nunca f-string a mensagem. `log.exception(...)` dentro de `except` (preserva traceback).
- `request_id` é contextvar populada pelo `LoggingMiddleware` (lê `X-Request-ID`); toda linha herda.
- `print()` é proibido no código propagado (`callbacks.py`, `streaming.py`, `chat.py` migrados).

---

## 14. Setup num projeto novo

1. Rode `scripts/sync_agents_to_another_fastapi_project.py --target <backend>`. Copia (overwrite) as
   camadas `agents/` + `src/api/**/agents`; copia (skip-if-exists) a infra compartilhada (logging,
   exceptions, middlewares, auth, uploads, models/repos de upload, `config/uploads.py`); copia
   `db/migrations/*.sql` preservando as do alvo.
2. Adicione as deps: langchain/langgraph/langchain-deepseek/langchain-groq/markitdown/asyncpg/orjson +
   **structlog** + **opencv-python-headless** + **numpy**; e `[tool.hatch]` `packages += ["agents"]`.
3. `DATABASE_URL` no `.env` → `dbmate up` (cria também `user_uploads`).
4. Wiring do §12 (logging + middleware + lifespan + routers + StaticFiles). Provider keys no `.env`.
5. **Auth:** substitua `resolve_identity` em `services/auth.py` por verificação JWT real (§4).
6. **Uploads org-owned:** se o projeto é org-owned, crie também `org_uploads` + `OrgUpload`/repo
   (o template ship só user-owned) — ver `uploads.md`.

> Tudo que era pendência (uploads universais, auth de chat, `print()`→structlog) está **implementado**
> no template — este doc descreve o estado atual, não um roadmap.
