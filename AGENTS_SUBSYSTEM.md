# Agents Subsystem — Canonical Spec

> **O que é este documento.** A especificação completa, tópico a tópico, do subsistema de
> agentes deste template (FastAPI + LangChain 1.x / LangGraph + asyncpg + dbmate). É a fonte
> de verdade do que o template **cria** e dos padrões que ele **força**. Pode ser enviado como
> prompt para um projeto novo recriar tudo de forma idêntica, ou usado como checklist de
> auditoria. Propaga via `backend/scripts/sync_agents_to_another_fastapi_project.py`.
>
> **Fonte canônica (decisão do usuário, 2026-09-30: "deixe tudo centralizado e padronizado em
> todos").** Este template é a ÚNICA origem da camada de IA de todos os apps (kailos, balizap,
> nexarena, optimuslar, akmeo). Melhoria feita num app volta para cá primeiro e sai pelo script
> de sync; `core/agents/` é copiado com overwrite, então edição local no app se perde. O
> checklist de convergência por app está no §17.

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
| `models.py` | `ModelConfig` (provider, pricing, capabilities, `provider_order` = jurisdição) + registro `Models` + `compute_cost_usd`/`round_cost_up` (`COST_DECIMAL_PLACES`) + `iter_model_configs` / `find_model_config` / `find_model_config_by_id` + `model_capabilities_dict` + `PROVIDER_ALIASES`/`canonical_provider`. |
| `model_catalog.py` | Modelos que o tenant pode escolher, com **label + preço** para a tela (`GET /agents/model-catalog`). Hoje só GLM 5.3 Flash; valida no import que todo slug existe no registro. (origem: akmeo) |
| `llm.py` | **Chamada one-shot** fora de agente: `complete()` (texto) e `complete_structured()` (Pydantic via function calling) + `UsageContext` (quem paga) + `LlmResult` (custo real/estimado) + `with_llm_retry` (CapacityLimiter do processo + retry só de erro transitório). (origem: akmeo `llm.py`) |
| `subagents.py` | `run_subagent()` + `SUBAGENT_RUN_TAG` — supervisor chama especialista como tool; especialista stateless (`checkpointer=False`), fora do stream do chat, custo sob `agent_id:<nome>`. |
| `tenant_instructions.py` | `tenant_instructions_middleware` — anexa o Markdown do tenant (`agent_configs`) ao system prompt base, em runtime, com memo TTL. |
| `tool_envelope.py` | Envelope `{"type", "data"}` para tool result virar card no front (`action_confirmation`/`action_error`). (origem: optimuslar) |
| `ocr.py` | `ocr_document()` — PDF escaneado / foto de documento → Markdown, 1 chamada GLM por página em paralelo, detecção de loop degenerado, página digital pula a rede. (origem: optimuslar `ocr_service`) |
| `custom_providers.py` | `init_model(cfg)` / `init_model_by_id(id)` + `init_<provider>_model`. `ChatOpenRouter` (reasoning + `model_provider` + custo real do upstream). |
| `callbacks.py` | `UsageRecorderCallback` — persiste 1 linha em `agent_message_usage` por chamada de LLM (metadata `thread_id`, `agent_id`, `user_id`, `client_id`, `tenant_id`). |
| `media.py` | Mídia em texto: `media_to_text(bytes, mime_type=..., usage=UsageContext, message_id=...)` com a cadeia Whisper (áudio) / GLM 5.3 Flash (imagem, **vídeo**) → `None`; `describe_images()` (N imagens numa chamada, devolve `VisionResult` com custo); retry por status; custo do Whisper lançado à mão. Sem acoplamento a canal — ver §8-B. |
| `checkpointer.py` | `AsyncPostgresSaver` singleton (`init_checkpointer`/`get_checkpointer`/`close_checkpointer`). |
| `history_window.py` | `sliding_window_middleware` — corta o histórico enviado ao LLM por orçamento de tokens/mensagens. |
| `prompt_cache.py` | Memo TTL in-process de fragmentos de prompt vindos do DB (instruções do tenant). NÃO é o cache do provedor — esse é implícito por prefixo (ver §10). |
| `schemas.py` | `AgentConfig`, `AgentSuggestion` (com `action: fill|attach`), serialização de sugestões. |

### `src/api/{models,repositories,routes,services}/agents/`
| Arquivo | Responsabilidade |
| --- | --- |
| `models/agents/usage.py` | `AgentMessageUsage` (Pydantic, espelha `agent_message_usage`). |
| `models/agents/history.py` | `ChatHistoryThread` (espelha `chat_history`). |
| `models/agents/checkpoint_jsonb.py` | `AgentCheckpoint`/`AgentCheckpointWrite` (value-objects do langgraph; pulado pelo check_schema). |
| `repositories/agents/usage.py` | `build_usage_from_ai_message`, `insert_agent_message_usage`, `get_thread_total_cost_usd`, `get_user_total_cost_usd`. |
| `repositories/agents/chat_history.py` | `get_chat_messages`, `save_chat` (upsert), `get_user_threads`, `delete_chat`. |
| `repositories/agents/agent_config.py` | `agent_configs` + `agent_config_versions` (upsert com bump atômico de versão, snapshots, listagem limitada). |
| `models/agents/agent_config.py` / `agent_config_version.py` | Espelho das tabelas de config do tenant. |
| `schemas/agents/agent_config.py` | DTOs de `/agents/{agent_id}/config` + `MAX_PROMPT_MARKDOWN_CHARS` (20k, espelha o CHECK e o front). |
| `routes/agents/agent_config.py` | `GET/PUT /agents/{id}/config`, `GET …/versions`, `POST …/versions/{v}/activate`. |
| `services/agents/agent_config.py` | get-or-default, salvar = nova versão + snapshot (transação), rollback = nova versão, invalida o memo. |
| `routes/agents/chat.py` | `POST /agents/chat/completions` (stream e não-stream) + extração multimodal. |
| `routes/agents/threads.py` | `GET/DELETE /agents/threads`, `GET /agents/threads/{id}`. |
| `routes/agents/models.py` | `GET /agents` — lista agentes com `capabilities`; `GET /agents/model-catalog`. |
| `services/agents/registry.py` | `discover_agents()` — auto-discovery da pasta `agents/`. |
| `services/agents/executors.py` | `call_agent_async`/`execute_agent` (agente do registry sem stream, **com metadata de custo**) + extração de reasoning. |
| `services/agents/streaming.py` | `stream_agent` — SSE + save destacado + tool/reasoning parts. |
| `services/agents/utils.py` | `convert_file_to_text` (MarkItDown). |

### Infra compartilhada (importada pelas camadas de agents; copiada skip-if-exists)
| Arquivo | Responsabilidade |
| --- | --- |
| `core/logging.py` | Stack structlog → stdlib → QueueHandler/QueueListener → stderr. `setup_logging`/`shutdown_logging`/`get_logger`/`bind_request_id`. JSON (orjson) em prod, console em dev. Config via `settings.logging` (yaml: `level`/`format`/`service_name`/`app_env`/`level_asyncpg`). |
| `core/exceptions.py` | `BadRequestError`/`AuthenticationError`/`ForbiddenError`/`NotFoundError` — subclasses de `HTTPException` (FastAPI trata nativo, sem handler custom). |
| `middlewares/logging_middleware.py` | `LoggingMiddleware` (ASGI puro) — lê `X-Request-ID`, bind em contextvar, 1 linha `http_request` por request com método/path/status/duration_ms. |
| `services/auth.py` | `get_auth_context` — seam única de identidade (Bearer → `X-User-Id` → `user` query → `default_user`). Ver §4. |
| `models/uploads/upload_jsonb.py` | `UploadKind`/`UploadVisibility`/`UploadAcl`/`UploadMetadata` (enums + JSONB shapes). |
| `models/uploads/user_upload.py` | `UserUpload` (espelha `user_uploads`; `owner_user_id: str`). |
| `repositories/uploads/user_upload_repository.py` | `UserUploadRepository` (create/update/find/soft_delete/hard_delete/find_by_entity). |
| `routes/uploads.py` | `POST /uploads` — gate capability + quota + dedup SHA-256 + `save_upload` + row em `user_uploads` (ver §8). |
| `config/uploads.py` | `save_upload` canônico (raw/image-AVIF/document) + `org_dir`/`user_dir` + filename `{slug}-{uuid4}.{ext}`. Core idêntico entre projetos. |

### `agents/<name>/` — agentes de exemplo (o contrato)
Cada um expõe `config: AgentConfig` + `create_root_agent(checkpointer=None)` + `tools/`:
`weather_agent/` (agente com tools — o caso comum), `web_search_agent/` (tools + scraping) e
`research_supervisor_agent/` (**subagente**: supervisor delega a um pesquisador via tool).

### `db/`
`db/migrations/<ts>_initial.sql` (dbmate) + `db/schema.sql`: cria `agent_message_usage`,
`chat_history`, `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `user_uploads` + função
`update_updated_at_column`. `20260930120000_tenant_agent_configs.sql`: `agent_message_usage.tenant_id`
(+ índice `(tenant_id, created_at)`), `agent_configs`, `agent_config_versions`.

### Frontend (`frontend/src/`)
`components/ai-elements/` (primitivas: Conversation, Message, Reasoning, PromptInput, Context…),
`components/chat/` (`ChatView`, `use-chat-session` = `useChat` + transport SSE, anexos, picker,
`tool-results/` = registry `type → card` do envelope, sugestões `fill|attach`),
`components/agent-config/` (tela de instruções do tenant — **canônica** para kailos/balizap/nexarena/akmeo,
ver §14), rota `routes/agent-config.tsx`, `lib/api.ts` (fetchers + `MAX_PROMPT_MARKDOWN_CHARS`).

---

## 2. Registro de modelos & stack única (OpenRouter GLM 5.3 Flash / Groq Whisper)

`ModelConfig` (frozen dataclass) em `core/agents/models.py`:

```python
@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    provider: str                      # openrouter | groq
    reasoning: bool = False            # emite reasoning_content no stream
    reasoning_effort: str | None = None  # low | medium | high  (OpenRouter)
    input_price_per_1m: float = 0.0
    cached_input_price_per_1m: float = 0.0
    output_price_per_1m: float = 0.0
    supports_image_input: bool = False
    supports_pdf_input: bool = False
    supports_audio_input: bool = False
    supports_video_input: bool = False
    provider_order: tuple[str, ...] = ()      # OpenRouter: upstreams preferidos, em ordem
    allow_provider_fallbacks: bool = True     # OpenRouter: False fixa em provider_order
```

**OpenRouter (gateway único de chat).** `model_id` é o slug do OpenRouter
(`z-ai/glm-5.3-flash`) e o mesmo modelo é servido por vários upstreams com preço, quantização e
jurisdição diferentes — `provider_order` declara os upstreams aceitos (`coreweave`, `fireworks`,
`deepinfra`, todos dos EUA) e `allow_provider_fallbacks=False` fixa nessa lista: um 429 reroteia
dentro dela em vez de cair em qualquer provedor do slug. Com `True` (default do dataclass) o gateway
reencaminha livremente. O pricing no `ModelConfig` é o do primeiro upstream e serve de fallback:
`usage.cost` reportado pelo OpenRouter (custo real do upstream roteado) vence (ver §7).

**Stack (USD por 1M tokens):**

| Uso | Modelo | input / cached / output | Notas |
| --- | --- | --- | --- |
| Texto, imagem e vídeo | OpenRouter `z-ai/glm-5.3-flash` (`Models.OpenRouter.GLM_5_3_FLASH`) | 0.15 / 0 / 0.50 | `reasoning_effort="high"`. Multimodal nativo: o mesmo modelo conversa e lê imagem/vídeo. Não aceita PDF nem áudio inline. |
| Áudio → texto | Groq `whisper-large-v3-turbo` (`Models.Groq.WHISPER_LARGE_V3_TURBO`) | 0.04 **por hora de áudio** | Não é chat model; POST multipart em `media.py` (ver §8-B). |

**Regra:** atendente padrão = GLM 5.3 Flash via OpenRouter; áudio passa antes pelo Whisper (Groq) em
`media.py`. Trocar de modelo = trocar 1 `ModelConfig` (as flags `supports_*` religam/desligam cada
ramo de mídia); o resto (custo, streaming, capabilities) acompanha automático.

---

## 3. Espectro de uso — escolha a menor ferramenta que resolve

| Caso | Use | Exemplo no template |
| --- | --- | --- |
| Uma pergunta → um texto (resumo, reescrita, "descreva", job agendado) | `llm.complete(prompt, usage=UsageContext(...))` | docstring de `core/agents/llm.py` |
| Uma pergunta → um objeto validado (extração, roteamento, score) | `llm.complete_structured(prompt, Schema, usage=...)` | docstring de `core/agents/llm.py` |
| Conversa com ferramentas, memória, stream e UI | agente em `agents/<name>/` (`create_agent`) | `agents/weather_agent/` |
| Tarefa que se divide em especialistas com loop próprio | supervisor + `run_subagent` | `agents/research_supervisor_agent/` |
| Áudio/imagem/vídeo chegando num fluxo de texto | `media.media_to_text` / `describe_images` | §8-B |
| PDF escaneado / foto de documento | `ocr.ocr_document` | docstring de `core/agents/ocr.py` |
| Resultado de tool como card no chat | `tool_envelope.action_confirmation(...)` | front `chat/tool-results/` |

Regras que valem para todos: **sempre passar `UsageContext`** em fluxo de produto (sem ele a
chamada não entra em `agent_message_usage` e escapa de qualquer teto); `agent_id` estável por
propósito (`"media-enrichment"`, `"lead-scoring"`) para saber quanto cada coisa custa; thread
sintético para trabalho fora de chat (`f"job:{job_id}"`).

## 3.1 Contrato do agente (limpo e resumido)

Cada `agents/<name>/agent.py` expõe:

```python
config = AgentConfig(
    name="...", description="...",
    system_prompt=SYSTEM_PROMPT,
    model=init_model(Models.OpenRouter.GLM_5_3_FLASH),
    tools=[tool_a, tool_b],
    save_to_db=True,
    capabilities=model_capabilities_dict(Models.OpenRouter.GLM_5_3_FLASH),
    suggestions=[...],
)

def create_root_agent(checkpointer=None):
    return create_agent(
        model=config.model,
        tools=config.tools,
        system_prompt=config.system_prompt,
        middleware=[sliding_window_middleware, tenant_instructions_middleware],
        checkpointer=checkpointer,   # injetado pelo registry
    )
```

Ordem do middleware: janela de histórico primeiro (corta o que o modelo vê), instruções do tenant
por último (anexam ao system prompt). Um agente que não deve ler instruções do tenant só omite o
segundo.

- **Auto-discovery** (`registry.py`): varre `agents/`, importa `agents.<name>.agent`, lê `config` +
  `create_root_agent` (ou `root_agent` pré-construído), injeta o checkpointer compartilhado quando
  `save_to_db=True`, e anexa o `usage_recorder` global. Chave do registro = `model_id` (`_`→`-`).
  Agente que falha no import sai no log como `agent_discovery_failed` (antes era engolido — o
  `web_search_agent` estava sumindo do picker em silêncio por sugestões em formato inválido).
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

Retorna `{"user_id", "client_id", "tenant_id", "roles"}`. `client_id` vem de `X-Client-Id`/`client_id`.
`tenant_id` é o escopo de config e de custo por tenant: no template = `user_id` (não há
organizações); nos apps = o `organization_id` resolvido do token verificado.

| Camada | Padrão no template | Como os apps reforçam |
| --- | --- | --- |
| Rotas de chat/threads/uploads | `ctx = Depends(get_auth_context)` → `user_id = ctx["user_id"]` (header/token, **nunca** o body). `threads` são owner-scoped (403 se outro dono). | Substituir `resolve_identity` por verificação JWT real (decode → `payload["sub"]`, raise `AuthenticationError`). |
| Rotas de gestão de config | n/a no template | kailos/balizap: `@permission_service.require_authentication()` + `require_permission_in_org("agent_config:read|manage")`, `user_id = request.state.auth_context["user_id"]`. |
| Webhook inbound (WhatsApp) | n/a no template | HMAC SHA-256 (`_verify_whatsapp_signature` + `WHATSAPP_APP_SECRET`); responde 200 ≤10s e processa via fila. |

`user_id`/`client_id`/`tenant_id` derivados da seam fluem para checkpointer config
(`configurable.tenant_id` → middleware de instruções), `usage_recorder` metadata e `chat_history`. **Frontend:** identidade vai no header `X-User-Id` em toda chamada (chat transport,
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

- **Reasoning/thinking:** extraído de `content[]` e de
  `additional_kwargs["reasoning_content"]`, reemitido como `reasoning-delta`.
- **Subagentes não vazam:** eventos com a tag `SUBAGENT_RUN_TAG` (`"nostream"`) são descartados —
  o usuário vê a tool `delegate_*` do supervisor, não os tokens do especialista.
- **Tool result como card:** saída `{"type", "data"}` (`tool_envelope.py`) é renderizada pelo
  registry do front; o resto cai no bloco de tool colapsado.

---

## 7. Contabilização de preço (input / cached / output)

- **Callback** `UsageRecorderCallback` (anexado globalmente no registry e via `config["callbacks"]`):
  em `on_chat_model_start` guarda metadata por `run_id`; em `on_llm_end` lê `usage_metadata` +
  `response_metadata`, resolve o `ModelConfig` (`find_model_config`) e insere em `agent_message_usage`.
- **Fórmula** (`compute_cost_usd`): `(fresh_input·in + cached·cached_in + output·out) / 1e6`, com
  `fresh_input = input_tokens - cache_read`, **arredondando para cima** (`round_cost_up`, nunca
  sub-cobra).
- **Custo reportado vence a tabela.** Gateway que roteia entre upstreams (OpenRouter) devolve o
  custo real da chamada em `usage.cost`; `ChatOpenRouter` expõe isso em
  `response_metadata["provider_cost_usd"]` (+ `upstream_provider`) e `build_usage_from_ai_message`
  prefere esse valor — a tabela estática só conhece o upstream preferido, e com fallback ligado o
  roteamento muda de request para request.
- **Tabela `agent_message_usage`:** `thread_id, message_id, user_id, client_id, agent_id, provider,
  model_id, input_tokens, cached_input_tokens, output_tokens, reasoning_tokens, total_tokens,
  cost_usd, error, created_at`. Imutável (sem `updated_at`).
- **Agregações:** `get_thread_total_cost_usd`, `get_user_total_cost_usd`,
  `get_tenant_cost_usd_since(tenant_id, month_start_utc())` — o custo do mês por tenant, base de
  qualquer teto de gasto (índice `(tenant_id, created_at)`; kailos/balizap fazem o mesmo com
  `organization_id`).
- **One-shot:** `llm.complete*` devolve `LlmResult.cost_usd` (real quando o OpenRouter reporta,
  `cost_is_real=True`) — útil para creditar o custo no teto assim que a chamada volta (akmeo). O custo também é embutido no
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

### B. Agente text-only (WhatsApp e afins) — `core/agents/media.py`
O atendente é um modelo de TEXTO e chega áudio, foto e PDF. `core/agents/media.py` é o degrau que
converte bytes em frase **antes** do prompt. **Entrada é `bytes` + `mime_type`, saída é `str | None`
— o módulo não conhece canal nenhum**, e é por isso que serve WhatsApp, e-mail ou uploads de chat
sem alteração; quem chama decide o que fazer com o `None` (no WhatsApp, um placeholder; num chat, o
anexo sem descrição).

```
áudio  → Whisper (Groq)        --falhou-->  None
imagem → GLM 5.3 Flash (OpenRouter)  --falhou-->  None
vídeo  → GLM 5.3 Flash (OpenRouter, parte `video_url`, até 20 MB inline)  --falhou-->  None
PDF    → não enriquecido inline (GLM não aceita PDF) → use `ocr.ocr_document` (página→imagem)
```

```python
text = await media_to_text(
    content, mime_type="audio/ogg", filename="audio.ogg",
    usage=UsageContext(thread_id=thread_id, agent_id=ENRICHMENT_AGENT_ID, tenant_id=org_id),
    message_id=str(message_id),
)
# N fotos numa chamada (laudo de avaliação kailos/balizap): o modelo compara os ângulos.
result = await describe_images([(jpeg1, "image/jpeg"), (jpeg2, "image/jpeg")],
                               prompt=LAUDO_PROMPT, context=listing_text, usage=ctx)
result.text, result.cost_usd
```

`UsageContext` (de `llm.py`) substitui os kwargs soltos `thread_id/agent_id/user_id` — é o mesmo
objeto em `llm.complete`, `media`, `ocr`, e é o que carrega `tenant_id` para o custo do mês.

Quatro decisões que o módulo encoda, e as três primeiras são exatamente onde os projetos que
copiaram esse padrão à mão erraram:

1. **Áudio é Whisper ou nada.** GLM 5.3 Flash não aceita áudio inline, então não há degrau
   multimodal de queda para áudio; transcrição é barata e dispensa raciocínio.
2. **A visão passa pelo LangChain** (`init_model(Models.OpenRouter.GLM_5_3_FLASH)` com
   `callbacks=[usage_recorder]`), e não pelo SDK cru. É o que faz a linha cair em
   `agent_message_usage` **de graça** — pelo atalho do SDK o custo da mídia simplesmente não existe
   para nenhum teto de gasto.
3. **O custo do Whisper é lançado à mão** (`record_transcription_cost`): ele é um POST multipart,
   não passa pelo callback, e é cobrado por **hora de áudio**. Tokens ficam em zero; o que importa
   é o `cost_usd`.
4. **Retry diferenciado e fail-soft.** 429/5xx tentam de novo (backoff exponencial, 2 tentativas);
   401/400 não — repetir credencial errada é queimar tempo numa falha que não muda de resposta.
   Cada falha sai no log **com o `status_code`**, porque "sem transcrição" por 401 e por 429 se
   resolvem de formas opostas. Nada aqui levanta.

**Ordem, no canal que chama.** Quem enfileira o trabalho tem que gravar o texto **antes** de
disparar o agente. Publicar "baixe a mídia" e "responda" no mesmo instante, sincronizados só por um
debounce fixo, é a corrida clássica: download lento → o agente lê o placeholder, responde "não
consigo ouvir áudio", e **nada o chama de volta** quando a transcrição fica pronta. O trigger sai
depois do enriquecimento — **inclusive quando ele falha**, porque silêncio é a pior degradação.

### Capability flags
`supports_image_input` é o único **enforçado** no chat playground (gate 415/400).
`supports_pdf/audio/video` são informacionais para o frontend — no fluxo MarkItDown todo não-imagem
vira texto — **e são o que `media.py` consulta** para saber qual modelo cobre qual modalidade.
Exposto em `GET /agents` via `model_capabilities_dict`.

**Modelo sem preço no registro lê custo ZERO em silêncio.** Foi o caso do `Groq.LLAMA_4_SCOUT`,
registrado sem preço e nunca referenciado; ele saiu, e o lugar dele é o
`Groq.WHISPER_LARGE_V3_TURBO` — que tem preço zerado **de propósito** (cobra por hora de áudio) e
não passa por `init_model`, então ninguém o roteia pelo caminho cobrado por token.

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
  início (quebra o provedor). O histórico completo continua no checkpoint para replay na UI.
- **Cache do provedor** (OpenRouter/GLM): implícito por **prefixo**, reportado em `cache_read` e
  cobrado a `cached_input_price_per_1m`. A única exigência é manter o prefixo estável: system prompt
  base estático primeiro, texto do tenant/dinâmico depois (é a ordem do
  `tenant_instructions_middleware`), nada de timestamp/request id no topo.
- **`prompt_cache.py`**: memo TTL in-process (`settings.agents.tenant_config_ttl_seconds`) das
  instruções do tenant — o middleware roda antes de CADA chamada de modelo do turno (loops de tool
  fazem várias). Salvar pela API invalida o worker que atendeu; os outros convergem no TTL.

---

## 11. Schema de banco (dbmate)

`db/migrations/<ts>_initial.sql` cria: `update_updated_at_column()`, `agent_message_usage`
(+índices client_id/created_at/thread_id), `chat_history` (+trigger updated_at, índices), as três
tabelas do langgraph `checkpoints`/`checkpoint_writes`/`checkpoint_blobs`, e `user_uploads`
(+CHECK `kind`/`visibility`, índices owner_user_id/entity/kind, trigger updated_at). **Schema
versionado via dbmate** (não `checkpointer.setup()` em runtime — sem DDL no startup). `db/schema.sql`
é o dump canônico, regenerado a cada `dbmate up`. `check_schema.py`: `UserUpload`→`user_uploads`,
`upload_jsonb.py` pulado (sufixo `_jsonb`).

`20260930120000_tenant_agent_configs.sql`: `agent_message_usage.tenant_id` + índice parcial
`(tenant_id, created_at)`, `agent_configs` (UNIQUE `(tenant_id, agent_id)`, CHECK de 20k chars, trigger
updated_at) e `agent_config_versions` (FK CASCADE, UNIQUE `(config_id, version)` cobre a FK).

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
stderr. `JSONRenderer`(orjson, NDJSON) em prod, `ConsoleRenderer` em dev (TTY-aware). Config vem de
`settings.logging` (`config/app/{env}.yaml > logging:` — `level`, `format: ""|json|console`,
`service_name`, `app_env`, `level_asyncpg`); `core/logging.py` não lê `os.getenv`.

- **Uso:** `from api.core.logging import get_logger` → `log = get_logger(__name__)`.
- Evento = `snake_case`, contexto = kwargs (`log.info("stream_agent_start", session_id=..., model=...)`).
  Nunca f-string a mensagem. `log.exception(...)` dentro de `except` (preserva traceback).
- `request_id` é contextvar populada pelo `LoggingMiddleware` (lê `X-Request-ID`); toda linha herda.
- `print()` é proibido no código propagado (`callbacks.py`, `streaming.py`, `chat.py` migrados).

---

## 14. Instruções do agente por tenant (config versionada)

O padrão kailos/balizap generalizado: o dono do negócio monta as instruções no ChatGPT (botão com
prompt pronto em `chatgpt-builder-prompt.ts`), cola na tela `/agent-config`, salva; o agente lê em
runtime.

- **Tabelas:** `agent_configs` (1 linha ativa por `(tenant_id, agent_id)`, `system_prompt_markdown`
  ≤ 20k chars, `model_id` do catálogo, `active_version`) + `agent_config_versions` (snapshot imutável
  por save). Salvar e restaurar SEMPRE criam versão nova — rollback é auditável e reversível.
- **API:** `GET/PUT /agents/{agent_id}/config`, `GET /agents/{agent_id}/config/versions` (50 mais
  recentes), `POST /agents/{agent_id}/config/versions/{v}/activate`, `GET /agents/model-catalog`.
  Tenant vem da seam (`ctx["tenant_id"]`), nunca do body. Apps com papéis colocam o check de
  permissão nas rotas (`agent_config:read|manage`).
- **Runtime:** `tenant_instructions_middleware` lê `configurable.tenant_id` + `metadata.agent_id`,
  busca o Markdown (memo TTL) e anexa depois do system prompt base, sob `## Instruções do negócio`.
  Sem tenant/config/DB → prompt base puro (instrução é enriquecimento, nunca motivo de falhar o turno).
  `model_id` hoje só alimenta a tela (catálogo de 1 modelo); com um 2º modelo, o swap entra no
  mesmo middleware (`request.override(model=init_model_by_id(...))`).
- **O que fica no app, não aqui:** dados do negócio injetados em runtime (horário, filas, catálogo),
  flags de captura (balizap `sections`), `enabled` on/off do atendente, preview/tester da config.
- **Frontend canônico (`components/agent-config/`, decisão 2026-10-01):** dois grupos de arquivo.
  *Apresentacionais* — copie **verbatim**, nunca importam `@/lib/api` (props + view-model
  `AgentVersionItem`): `InstructionsCard`, `VersionsPanel` (+ `VersionPreviewDialog`, `text-diff.ts`,
  `agent-version.ts`), `MarkdownPreview` (Streamdown), `chatgpt-builder-prompt.ts`. *Ligados à API* —
  o app adapta ao seu backend/permissão: `use-agent-config.ts` e `AgentConfigScreen.tsx`.
  - `<InstructionsCard markdown maxChars builderContext? saving readOnly? title? description?
    onSave(markdown, note?) />` — passos numerados, botão "Montar com o ChatGPT", textarea mono com
    contador/limite, nota de publicação opcional (`note`, ≤500, vai no PUT), preview renderizado.
    Monte com `key={activeVersion}` (save/restore remonta em leitura; save que falhou mantém o rascunho).
  - `<VersionsPanel versions activeVersion isLoading? canActivate? activatingVersion onActivate />` —
    "Ver" abre `VersionPreviewDialog` (aba Texto + aba Diferenças vs. versão ativa, diff de linhas);
    "Restaurar" cria versão NOVA (sem confirm: nada se perde).
  - `<AgentConfigScreen agentId onAgentChange builderContext? canEdit? renderBeforeInstructions?
    renderAfterInstructions? />` — slots `(ctx: {agentId, config}) => ReactNode` p/ extras do app
    (toggle on/off antes; tester/documentos/captura entre instruções e histórico) sem importá-los aqui.
    A tela NÃO seta largura/scroll: o layout dita (a rota do template embrulha com 1440 só porque o
    `SidebarLayout` do template é cru).
  - **Prompt do ChatGPT:** o app só fornece texto de domínio via `ChatGptBuilderContext`
    (`platformName`, `channel`, `businessName`, `businessDescription`, `knownFacts`, `platformHandles`,
    `tools`, `domainTopics`, `domainSections`, `deliveryTitle`); o esqueleto (contexto → "a plataforma
    JÁ cuida disto" → entrevista → UM bloco Markdown) é fixo. `buildChatGptBuilderUrl(context)`;
    URL codificada < ~4k chars. Sempre preencha `platformHandles` com o que o SEU runtime injeta.

## 15. Setup num projeto novo

1. Rode `scripts/sync_agents_to_another_fastapi_project.py --target <backend> [--add-module NAME]... [--examples]`.
   Sobrescreve **arquivo a arquivo** só o que o template possui (nunca apaga nada do alvo):
   `src/api/{schemas,models,repositories,services,routes}/agents`; em `core/agents/` só os módulos
   que o alvo **já tem** (módulo novo só com `--add-module ocr`, repetível); imprime resumo
   overwritten/added/unchanged/skipped. Copia
   (skip-if-exists) a infra compartilhada (logging, exceptions, middlewares, auth, uploads, models/repos
   de upload, `config/uploads.py`); copia `db/migrations/*.sql` preservando as do alvo; `--examples`
   copia os agentes de exemplo (skip-if-exists).
2. Adicione as deps: langchain/langgraph/langchain-openai/markitdown/asyncpg/orjson/curl-cffi/anyio/pyyaml +
   **structlog** + **opencv-python-headless** + **numpy** (+ **pypdfium2** se usar `ocr.py`); e
   `[tool.hatch]` `packages += ["agents"]`.
3. `DATABASE_URL` no `.env` → `dbmate up`. Config: chaves yaml `openrouter:`/`agents:` (incl.
   `max_concurrent_llm`, `llm_max_retries`, `tenant_config_ttl_seconds`) nos 3 `config/app/*.yaml` +
   campos em `Settings` + secrets no `.env` (o script imprime o passo a passo).
4. Wiring do §12 (logging + middleware + lifespan + routers + StaticFiles). Provider keys (`OPENROUTER_API_KEY`, `GROQ_API_KEY`) só no `.env`.
5. **Auth:** substitua `resolve_identity` em `services/auth.py` por verificação JWT real e devolva
   `tenant_id` (org do usuário) no contexto (§4).
6. **Uploads org-owned:** se o projeto é org-owned, crie também `org_uploads` + `OrgUpload`/repo
   (o template ship só user-owned) — ver `uploads.md`.
7. **Frontend:** copie `components/{ai-elements,chat,agent-config}/`, a rota `agent-config` e os
   fetchers de `lib/api.ts`. Em `agent-config/` só `use-agent-config.ts`/`AgentConfigScreen.tsx` são
   adaptados (§14); passe o `builderContext` do seu domínio.

## 16. Como estender e propagar (para o próximo agente)

- **Novo modelo:** só se a regra `ai-agents.md` mudar. Um `ModelConfig` em `models.py` + uma
  `ModelOption` em `model_catalog.py` + migration reescrevendo slugs legados. Nada mais muda.
- **Novo agente:** pasta `agents/<name>/` com `agent.py` (`config` + `create_root_agent`) e `tools/`.
  O registry descobre sozinho. Comece copiando `weather_agent`.
- **Nova capacidade genérica** (helper de mídia, middleware, envelope de tool): nasce em
  `core/agents/` com docstring de módulo dizendo quando usar e de qual app veio; entra na tabela do
  §1 e no espectro do §3. Lógica de negócio (dispatcher de WhatsApp, laudo, handoff, runner de
  agendamento) fica no app.
- **Política de `core/agents/` num app:** o app mantém SÓ os módulos que realmente usa (direta ou
  transitivamente), cada um **byte-idêntico** ao template (`cmp`); módulo não usado é apagado (puxa
  dep que o app não tem — ex.: `ocr.py` exige pypdfium2). Comportamento específico do app vive em
  adaptadores **fora** de `core/agents/`. Dica de domínio (vocabulário de placa, matrícula, número de
  peito) entra pelo kwarg `extra_instructions` de `ocr_document`/`describe_media`/`describe_images`/
  `media_to_text`, que é ANEXADO ao prompt canônico, nunca o substitui.
- **Propagar:** rode o sync em cada app, revise o diff (o overwrite apaga edições locais nos arquivos
  do template — melhoria volta ao template primeiro), ajuste os pontos de acoplamento do §17 e rode o
  `check.sh` do app.

## 17. Checklist de convergência por app (estado em 2026-09-30)

> Convergência concluída em 2026-09-30: todo módulo presente em `core/agents/` de cada app é idêntico ao
> template; módulos não usados foram removidos e dicas de domínio vão por `extra_instructions` nos
> call sites (fora do core). Os itens abaixo são o histórico do que foi levado para adaptadores.

Divergências encontradas ao consolidar. Cada app deve, ao rodar o sync:

- **Todos:** `custom_providers.py` lendo chaves de `config.integrations` (hoje kailos, balizap,
  optimuslar, akmeo usam `os.getenv` + `dotenv.load_dotenv`; nexarena usa `settings` direto — os dois
  convergem para o shim `integrations_config`); `models.py` com `iter_model_configs`;
  `media.py` com a nova API `usage=UsageContext` (callers: `media_to_text(..., usage=..., message_id=...)`);
  `tenant_id` na seam de auth; middleware `sliding_window` + `tenant_instructions` nos agentes de chat.
- **kailos:** `organization_id UUID` em `agent_message_usage` ≈ `tenant_id` — manter a coluna do app
  e mapear no callback (passar `tenant_id=str(org_id)`; `_as_uuid` fica no app), ou migrar para
  `tenant_id`. `usage_repository.py` → nome do template `repositories/agents/usage.py`.
  `describe_images` do app → o do template (retorna `VisionResult`, não tupla). Config do atendente
  (`org_agent_configs`) continua do app; o front `agent-config/` segue o canônico do §14.
- **balizap:** mesmo mapeamento `organization_id`→`tenant_id`; `media.py` (CurlMime, sem retry, sem
  custo do Whisper) → template; `schemas.py` ganha `action` nas sugestões. `org_agent_configs` +
  `AgentTester`/`ModelSetup`/`DocumentAiConfig` ficam no app, plugados pelos slots da
  `AgentConfigScreen` (fonte canônica da tela: §14).
- **nexarena:** `callbacks.py` grava `conversation_id` e usa `agent_message_usage_repository` — adotar o
  repo do template (`insert_agent_message_usage`) e levar `conversation_id` como `thread_id`/metadata
  do app; `custom_providers` perde `streaming=False` fixo (o template recebe `streaming` por kwarg).
- **optimuslar:** `tool_envelope.py` → template (manter os discriminadores `appraisal_*` num módulo do
  app); `schemas.py`: `CAPABILITY_OCR_INPUT` fica no app (flag de agente, não de modelo — ver §8);
  `services/documents/ocr_service.py` + `page_render_service.py` → `core/agents/ocr.ocr_document`
  (pypdfium2; mesma heurística de scan/coverage).
- **akmeo:** `services/agents/llm.py` → `core/agents/llm.py` (`with_llm_retry`, `cost_of`,
  `complete`); `model_catalog.py` → `core/agents/model_catalog.py` (`description_pt`→`description`,
  `ModelOption.config`); faltam `callbacks.py`/`media.py`/`checkpointer.py` — o runner credita custo à
  mão, deveria passar `UsageContext` para o `usage_recorder` gravar `agent_message_usage`.

> Tudo que era pendência (uploads universais, auth de chat, `print()`→structlog) está **implementado**
> no template — este doc descreve o estado atual, não um roadmap.
