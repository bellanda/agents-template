---
name: ai-agents
description: PORTÃO obrigatório de TUDO que é IA dentro de um app (stack única, decisão 2026-09-30, fonte canônica `~/code/github-templates/agents-template`). INVOCAR ANTES de QUALQUER trabalho com LLM — chamada one-shot (`llm.complete`), saída estruturada (`complete_structured`, extração/roteamento/score), agente com tools (`create_agent`, `agents/<name>/`, `@tool`), subagente/delegação (`run_subagent`, supervisor), chat com streaming SSE (`/agents/chat/completions`, `stream_agent`, threads, interrupção), frontend de IA (`ai-elements`, `use-chat-session`/`useChat`, cards de tool result/`tool_envelope`, anexos, reasoning, custo/contexto, sugestões), mídia (imagem/vídeo via GLM, áudio via Groq Whisper, OCR de PDF escaneado, `media.py`/`ocr.py`), custo/uso por tenant (`UsageContext`, `agent_message_usage`, teto de gasto), history window, prompt cache, checkpointer, config/instruções de agente por tenant (Markdown, versões, botão ChatGPT, `agent_configs`), catálogo de modelos, handoff humano, adicionar agente/tool novo e propagar o template (`sync_agents_to_another_fastapi_project.py`). Checklist de invariantes + tabela "qual ferramenta usar" + roteia pras references. NUNCA provedor fora de OpenRouter GLM 5.3 Flash (texto/imagem/vídeo) e Groq Whisper (áudio); NUNCA chamar LLM sem `UsageContext`; NUNCA SDK cru de provedor (sempre `init_model`); NUNCA reimplementar `core/agents/` num app (nasce no template e propaga); NUNCA agente quando `complete`/`complete_structured` resolve.
---

# AI Agents — O Portão

Ponto de entrada único de IA dentro de app. **NUNCA escreva código que chama LLM, monta agente, tela de
chat ou config de agente sem passar por aqui.** A rule `ai-agents.md` fixa a stack (invariante); este
skill é o "como" padronizado. Decisão do usuário (2026-09-30): tudo de IA é **centralizado e idêntico
em todos os apps** (kailos, balizap, nexarena, optimuslar, akmeo).

**Fonte canônica:** `~/code/github-templates/agents-template` (`AGENTS_SUBSYSTEM.md` = spec completa,
`backend/src/api/core/agents/` = infra, `backend/agents/` = exemplos, `frontend/src/components/{ai-elements,chat,agent-config}/`).
`core/agents/` é copiado com OVERWRITE nos apps — edição local se perde. Melhoria feita num app volta
pro template primeiro (ver `references/propagation.md`).

## Stack fixa (não discutir)

| Modalidade | Provedor | Modelo |
| --- | --- | --- |
| Texto, tools, extração, imagem, vídeo | OpenRouter | GLM 5.3 Flash — `Models.OpenRouter.GLM_5_3_FLASH` |
| Áudio → texto | Groq | `whisper-large-v3-turbo` (só se o app recebe áudio) |

Secrets: só `OPENROUTER_API_KEY` e `GROQ_API_KEY`. Proibido DeepSeek/Gemini/OpenAI/Anthropic direto/etc.
GLM não aceita PDF nem áudio inline → PDF escaneado = `ocr.py`, áudio = Whisper.

## Qual ferramenta usar (escolha a MENOR que resolve)

| Situação | Use | Onde |
| --- | --- | --- |
| Um prompt → um texto (resumo, reescrita, descrição, job agendado) | `llm.complete(prompt, usage=…)` | `one-shot-structured.md` |
| Um prompt → objeto validado que CÓDIGO lê (extração, roteamento, score, classificação) | `llm.complete_structured(prompt, Schema, usage=…)` | `one-shot-structured.md` |
| Pipeline de N passos fixos (extrai → decide → age) | N × `complete*` encadeados em service/job; NÃO agente | `one-shot-structured.md` |
| Conversa com ferramentas, memória, stream e UI de chat | agente `agents/<name>/` (`create_agent`) | `agents-and-tools.md` |
| Especialista com prompt/tools próprios ou loop longo que incharia o contexto | supervisor + `run_subagent` | `subagents.md` |
| Áudio/foto/vídeo chegando num fluxo de texto | `media.media_to_text` / `describe_images` | `media-ocr.md` |
| PDF escaneado / foto de documento | `ocr.ocr_document` | `media-ocr.md` |
| Tool que deve virar card no chat | `tool_envelope.action_confirmation/tool_result` + registry do front | `frontend-chat.md` |
| Dono do negócio edita o que o agente diz | `agent_configs` + `tenant_instructions_middleware` | `tenant-config.md` |
| IA passa cliente para humano | gate `integrations` → `human-handoff-queues.md` | (fora daqui) |

Regra de bolso: **se o fluxo é determinístico, não é agente.** Agente = o MODELO decide quais tools chamar
e quantas vezes. Se código decide a sequência, use `complete*` (mais barato, testável, sem checkpointer).

## Checklist de build (em ordem; só desça o que a tarefa exige)

- [ ] **1. Escolha da ferramenta.** Passou pela tabela acima? Justifique agente/subagente; o default é
  one-shot. → tabela + `one-shot-structured.md`.
- [ ] **2. Modelo via registry.** `Models.OpenRouter.GLM_5_3_FLASH` + `init_model(cfg)`/`init_model_by_id`.
  Nunca `ChatOpenAI(...)`/SDK de provedor direto, nunca slug hardcoded. → `usage-cost.md` (modelos).
- [ ] **3. `UsageContext` em TODA chamada de produto.** `thread_id` + `agent_id` estáveis por propósito
  (`f"job:{id}"` p/ fora de chat), `tenant_id` preenchido. Sem ele a chamada escapa de custo e de teto.
  → `usage-cost.md`.
- [ ] **4. Agente novo?** Pasta `agents/<name>/` (`config` + `create_root_agent`), copie `weather_agent`;
  middleware `[sliding_window_middleware, tenant_instructions_middleware]` nessa ordem; o registry
  descobre sozinho. → `agents-and-tools.md` (+ `propagation.md` §"Adicionar agente/tool").
- [ ] **5. Tools.** `@tool("name", args_schema=Pydantic)`, docstring = o que o LLM lê; falha ESPERADA →
  `action_error(...)` (não raise); escrita → `action_confirmation(...)`. → `agents-and-tools.md`.
- [ ] **6. Mídia/OCR.** Áudio=Whisper (grava texto ANTES de disparar o agente), imagem/vídeo=GLM via
  LangChain (nunca SDK cru), PDF escaneado=`ocr.py`. Uploads seguem o gate `uploads-storage`. → `media-ocr.md`.
- [ ] **7. Chat/streaming (backend).** Identidade SEMPRE da seam `get_auth_context`, nunca do body;
  SSE protocolo Vercel AI SDK v5; subagente não vaza no stream; save destacado na interrupção.
  → `streaming-backend.md`.
- [ ] **8. Frontend de IA.** Gate `frontend` primeiro (layout/overlay), depois `frontend-chat.md`:
  componentes `ai-elements` + `use-chat-session`; card de tool = entrada no registry, não `if` em
  `ChatMessage`; `accept=` do picker vem de `capabilities`.
- [ ] **9. Config do agente por tenant.** Markdown único ≤ 20k chars, versões imutáveis, botão ChatGPT,
  `tenant_id` da seam (nunca do body). → `tenant-config.md` (+ `frontend/references/agent-instructions.md`).
- [ ] **10. Contexto & cache.** `sliding_window_middleware` em agente de chat; prefixo do prompt ESTÁTICO
  (base → tenant → dinâmico; nada de timestamp/request id no topo). → `usage-cost.md`.
- [ ] **11. Propagação.** Mudou `core/agents/`, `routes|services|repositories|models|schemas/agents/`,
  migration de agentes ou front de chat? Mude no TEMPLATE, rode o sync. → `propagation.md`.

## Invariantes não negociáveis (sempre)

- Só OpenRouter + GLM 5.3 Flash e Groq Whisper; nada de provedor novo no registry/`Settings`/`.env.example`/deps.
- Toda chamada de modelo passa por `init_model*` (callback de custo `usage_recorder` vem junto); toda
  chamada de produto leva `UsageContext`. Mídia por SDK cru = custo invisível = bug.
- `complete_structured` usa `function_calling` (não `json_schema`) e reasoning OFF por default; erro de
  parse LEVANTA — trate no caller, não engula.
- Retry só de erro transitório (429/5xx/timeout) e concorrência limitada por `settings.agents.max_concurrent_llm`
  (`with_llm_retry`); 401/400 não repetem.
- Custo reportado pelo OpenRouter (`provider_cost_usd`) vence a tabela estática; arredonda pra CIMA.
- Identidade/`tenant_id` de agente vêm da seam de auth/token verificado, **nunca** do body/query do cliente.
- Subagente: `checkpointer=False`, tag `SUBAGENT_RUN_TAG`, `agent_id` com sufixo `:<nome>`.
- Instrução do tenant é enriquecimento: falha/ausência → prompt base puro, nunca quebra o turno.
- Schema de agentes via dbmate (gate `database`), nunca `checkpointer.setup()` em runtime.
- Logs: structlog (`log.info("snake_case_event", k=v)`), nunca `print()`; nunca logar conteúdo de mensagem/PII.
- Não use sem uso: app sem áudio não carrega `media.py`/Groq; sem OCR não carrega `ocr.py`/pypdfium2.
- Sem testes a menos que o usuário peça (regra global).

## References

- `references/one-shot-structured.md` — `complete`/`complete_structured`, `LlmResult`, retry/limiter, pipelines.
- `references/agents-and-tools.md` — contrato `agents/<name>/`, `create_agent`, tools, middleware, registry, checkpointer.
- `references/subagents.md` — supervisor + `run_subagent`, quando delegar, invariantes.
- `references/streaming-backend.md` — `POST /agents/chat/completions`, SSE, threads, interrupção, auth seam.
- `references/frontend-chat.md` — ai-elements, `use-chat-session`, cards de tool, anexos, reasoning, custo/contexto, sugestões.
- `references/media-ocr.md` — imagem/vídeo (GLM), áudio (Whisper), PDF OCR, uploads no chat.
- `references/usage-cost.md` — modelos/registry, `agent_message_usage`, custo por tenant/teto, history window, prompt cache.
- `references/tenant-config.md` — instruções por tenant (Markdown, versões, ChatGPT), catálogo de modelos, handoff (rotas).
- `references/propagation.md` — sync script, adicionar agente/tool/modelo, convergência por app.

Skills vizinhos: `database` (migrations/repos), `frontend` (layout, `agent-instructions.md`),
`integrations` (WhatsApp/Meta, `human-handoff-queues.md`), `uploads-storage`, `anyio-concurrency`,
`python-config-bootstrap` (yaml `agents:`/`openrouter:`), `pdf-processing`, `http-client`.
