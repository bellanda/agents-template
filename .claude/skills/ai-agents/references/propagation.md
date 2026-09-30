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
uv run scripts/sync_agents_to_another_fastapi_project.py --target /caminho/app/backend [--add-module ocr]... [--examples] [--optional]
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

## Convergência por app (estado 2026-09-30; detalhe no §17 do AGENTS_SUBSYSTEM)

- **Todos:** `custom_providers` lendo `config.integrations` (shim `integrations_config`); `iter_model_configs`;
  `media_to_text(..., usage=UsageContext, message_id=...)`; `tenant_id` na seam; middlewares `sliding_window` +
  `tenant_instructions`.
- **kailos/balizap:** `organization_id` ≈ `tenant_id` (mapear no callback ou migrar); `media.py` do template
  (retry + custo do Whisper); `org_agent_configs` fica no app até convergir; sugestões ganham `action`.
- **nexarena:** usar `insert_agent_message_usage` do template; `conversation_id` como `thread_id`; sem
  `streaming=False` fixo em `custom_providers`.
- **optimuslar:** `tool_envelope` → template (discriminadores `appraisal_*` no app); `ocr_service` →
  `core/agents/ocr.ocr_document`.
- **akmeo:** `llm.py`/`model_catalog.py` → template; adotar `callbacks`/`media`/`checkpointer`; runner passa
  `UsageContext` em vez de creditar custo à mão.
- Nenhum app mantém provedor fora da stack (DeepSeek/Gemini/OpenAI/etc.) nem secret sem leitor.
