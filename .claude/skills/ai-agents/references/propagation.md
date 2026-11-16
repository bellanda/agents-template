# Propagação, extensão e convergência

> Reference do gate `ai-agents`. Canônico: `backend/scripts/sync_agents_to_another_fastapi_project.py` (docstring
> lista tudo que copia) e AGENTS_SUBSYSTEM.md §15–§17.

## Regra de ouro

O template é a ÚNICA origem da camada de IA. Mudança de estrutura nasce em
`~/code/github-templates/agents-template` → sync nos apps. Melhoria feita num app volta ao template
primeiro (senão o próximo sync apaga). Lógica de negócio (dispatcher WhatsApp, laudo, handoff, runner de
agendamento) fica no app.

## Rodar o sync

```bash
cd ~/code/github-templates/agents-template/backend
uv run scripts/sync_agents_to_another_fastapi_project.py --target /caminho/app/backend [--add-module ocr|media|speech]... [--examples] [--optional]
```

- **Overwrite por ARQUIVO** (só o que o template possui; NUNCA apaga arquivo do alvo — adaptadores e
  arquivos do app sobrevivem): `src/api/{schemas,models,repositories,services,routes}/agents/`. Em
  `core/agents/` só sobrescreve módulos que o alvo JÁ tem; módulo novo exige `--add-module NAME`
  (repetível). O script imprime resumo overwritten/added/unchanged/skipped.
- **Política do app:** mantém SÓ os módulos de `core/agents/` que usa (direta/transitivamente), cada um
  byte-idêntico ao template (`cmp`); não usado = apagado. Customização fica em adaptador fora do core;
  dica de domínio via `extra_instructions` (ver `media-ocr.md`).
- **Skip-if-exists** (deps compartilhadas): middlewares, models/repos de upload, `core/{logging,exceptions}.py`,
  `services/auth.py`, `routes/uploads.py`, `config/uploads.py`; migrations `db/migrations/*.sql` (as do alvo
  ficam). `--examples` copia `agents/{weather,web_search,research_supervisor}_agent`.
- **Impresso (manual):** deps do `pyproject`, `[tool.hatch] packages += ["agents"]`, wiring do lifespan/routers,
  `dbmate up`, chaves yaml `openrouter:`/`agents:` nos 3 `config/app/*.yaml` + `Settings` + secrets no `.env`.
- **Frontend NÃO é copiado pelo script:** copie à mão `components/{ai-elements,chat,agent-config}/`, rota
  `agent-config` e fetchers de `lib/api.ts`.
- Depois: `git diff` do alvo (overwrite apaga edição local nos arquivos do template), ajuste acoplamentos do §17,
  rode o `check.sh` do app (nunca durante workflow multi-agente ativo).
- Deps de IA: langchain/langgraph/langchain-openai/markitdown/asyncpg/orjson/curl-cffi/anyio/pyyaml/structlog,
  + `opencv-python-headless` + `numpy` + **`pypdfium2`** (só se usar `ocr.py`). Sem pymupdf. Dep NOVA fora
  dessa lista = proponha antes.

## Adicionar agente

1. `agents/<name>/agent.py` (`config` + `create_root_agent`) + `tools/` — copie `weather_agent`.
2. Tools com `@tool(args_schema=…)`; card → envelope + registry do front (`frontend-chat.md`).
3. `capabilities=model_capabilities_dict(...)`, sugestões válidas (formato inválido faz o agente sumir do picker).
4. Reinicie: o registry descobre. Verifique `GET /agents` e o log `agent_discovery_failed`.
5. Agente genérico e reutilizável → nasce no template (`--examples`); específico do produto → só no app.

## Adicionar tool / capacidade genérica

Tool do app: no `agents/<name>/tools/` do app. Helper/middleware/envelope genérico: `core/agents/` **do
template**, com docstring de módulo (quando usar + app de origem), linha na tabela do §1 e no espectro do §3
de `AGENTS_SUBSYSTEM.md`, e uma linha nas references deste skill. Discriminador de card novo: backend + registry.

## Adicionar modelo (raro)

Só se a rule `ai-agents.md` mudar. Um `ModelConfig` (com preço, `provider_order`) em `models.py` + `ModelOption`
em `model_catalog.py` + migration reescrevendo slugs legados. Atualize a rule, a tabela da SKILL e o §2.

## Convergência por app (estado REAL medido em 2026-11-13, auditoria skills-backend-04)

O template é a origem, mas NEM TUDO que os apps têm nasceu nele: o template traz
`services/agents/manipulation_guard.py` (contador Valkey + decisão + textos fixos genéricos, com testes em
`tests/agents/test_manipulation_guard.py`; padrão da frota desde 2026-11-16, byte-idêntico em kailos/emporion/nexarena), mas NÃO traz a tool `report_manipulation_attempt` nem o
`forced_reply` (código de app); `run_subagent` existe só no template (0 apps usam). **"Copiar do template"
NÃO entrega a segurança de chatbot completa nem a instrução por tenant**; confira a tabela antes de assumir. `sync_agents…` copia por arquivo; módulo que o app não tem
exige `--add-module`.

Módulos de `backend/src/api/core/agents/` por app (S = presente):

| Módulo | template | kailos | emporion | nexarena | optimuslar | akmeo | promoservice |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ai_budget`, `llm_limits`, `run_limits` (2026-11-13) | S | S | S | S | S | S | sem IA |
| `custom_providers`, `models`, `llm`, `callbacks` | S | S | S | S | S | S | — |
| `checkpointer` + `asyncpg_saver` | S | S | S | S | S | não | — |
| `checkpoint_retention` | S | job em `cron/` | não | não | S | não | — |
| `history_window`, `empty_reply_guard` | S | S | S | S | não | não | — |
| `media` (Whisper/imagem) | S | S | S | S | não | não | — |
| `ocr` | S | não | S | não | S | não | — |
| `speech` (TTS) | S | S | não | não | não | não | — |
| `tenant_instructions` (middleware de instrução por tenant) | S | via `agents/*/agent.py` + `agent_config` | via `agents/whatsapp_attendant` | NÃO | NÃO | NÃO | — |
| `tool_envelope` | S | não | não | não | S (`appraisal_*` no app) | não | — |
| `scenario_checks`/`scenario_replay` | S | no agente | S | S | não | não | — |
| `model_catalog` | S | no app | no app | no app | no app | S | — |
| `subagents` (`run_subagent`) | S | não | não | não | não | não | — |
| Guarda de manipulação: `services/agents/manipulation_guard.py` (S no template) · tool `report_manipulation_attempt` + `forced_reply` (código de app) | guard S, tool NÃO | S (`agents/vehicle_sales_agent/tools.py`; follow-up em `portals/whatsapp/agent_followup.py`) | S (`agents/whatsapp_attendant/tools.py`; follow-up idem) | S (`services/agents/tools.py`; follow-up `whatsapp/agent_followup.py`; tenant fixo `MANIPULATION_TENANT` em `agents/identity.py`) | n/a (chat só de usuário logado) | n/a (agentes internos) | n/a (sem IA) |

- **Sync e `manipulation_guard.py`:** o arquivo é idêntico ao do template em todos os apps (textos
  genéricos, sem palavra de negócio), então o sync é seguro: nada do app mora nele. A fiação do app é a tool
  `report_manipulation_attempt` + `forced_reply` + o handoff (código de app, chama `register_manipulation_attempt`),
  assim como a política de teto por organização
  (`services/agents/ai_budget.py` de kailos/emporion/akmeo; o canônico `core/agents/ai_budget.py` já está no template). `models.py` tem 2 variantes (kailos +
  template × akmeo/emporion/nexarena/optimuslar); akmeo ainda sem `history_window`/media/checkpointer.
- **Novos em `core/agents/` (2026-11-13), copiados sem edição para os 5 apps de IA com `core/agents/` (`checkpoint_retention` só no optimuslar; kailos roda a retenção como job em `cron/`):** `llm_limits`
  (guarded_call/guarded_stream; `max_concurrent_llm` é por processo), `run_limits` (`run_limits_config`
  + `bounded_events`), `ai_budget` (teto canônico) e `checkpoint_retention`. O `sync_agents…` só
  sobrescreve módulo que o alvo JÁ tem: app sem eles precisa de `--add-module llm_limits --add-module
  run_limits --add-module ai_budget --add-module checkpoint_retention` (a lista de `CORE_AGENTS` do script
  não os nomeia — pendência do template). `routes/agents/` está em `COPY_TARGETS` (OVERWRITE) e passa a
  depender de `services/uploads/upload_access_service` (`resolve_authorized_upload`): o alvo precisa dele
  antes do sync.
- Todos: `custom_providers` lendo `config.integrations` (shim `integrations_config`); `iter_model_configs`;
  `media_to_text(..., usage=UsageContext, message_id=...)` onde há `media`; `tenant_id` na seam.
  O middleware `sliding_window` está em kailos, emporion, nexarena, optimuslar (não em akmeo);
  `tenant_instructions` só onde a tabela diz — NÃO é universal.
- **kailos/emporion:** `organization_id` ≈ `tenant_id`; `org_agent_configs` fica no app até convergir;
  sugestões ganham `action`.
- **nexarena:** usar `insert_agent_message_usage` do template; `conversation_id` como `thread_id`; sem
  `streaming=False` fixo em `custom_providers`; sem instrução por tenant ainda.
- **optimuslar:** `tool_envelope` já é o do template (discriminadores `appraisal_*` no app); `ocr_service` →
  `core/agents/ocr.ocr_document`; sem `media`/`history_window`.
- **akmeo:** `llm.py`/`model_catalog.py` no template; falta adotar `checkpointer`/`media`/`history_window`;
  runner passa `UsageContext` em vez de creditar custo à mão.
- Nenhum app mantém provedor fora da stack (DeepSeek/Gemini/OpenAI/etc.) nem secret sem leitor.
