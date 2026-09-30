# Config do agente por tenant e catálogo de modelos

> Reference do gate `ai-agents`. Canônico: AGENTS_SUBSYSTEM.md §14; backend `core/agents/{tenant_instructions,
> prompt_cache,model_catalog}.py`, `routes|services|repositories/agents/agent_config.py`; front
> `components/agent-config/`. Tela (anatomia, UX, botão ChatGPT) → `frontend/references/agent-instructions.md`
> (NÃO duplicar aqui). Handoff humano/equipes → `integrations/references/human-handoff-queues.md`.

## Contrato

O dono do negócio monta as instruções no ChatGPT (botão com prompt pronto, `chatgpt-builder-prompt.ts`), cola
em `/agent-config`, salva; o agente lê em runtime. **Um Markdown só** (≤ 20.000 chars = `MAX_PROMPT_MARKDOWN_CHARS`,
mesmo teto do CHECK SQL e do front). Sem formulário que compila Markdown, sem "modo guiado/avançado".

## Dados

- `agent_configs`: 1 linha ativa por `(tenant_id, agent_id)` (UNIQUE), `system_prompt_markdown`, `model_id`
  (do catálogo), `active_version`.
- `agent_config_versions`: snapshot imutável por save (FK CASCADE, UNIQUE `(config_id, version)`).
- **Salvar e restaurar SEMPRE criam versão nova** (bump atômico na transação) — rollback auditável e reversível.

## API (tenant sempre de `ctx["tenant_id"]`, nunca do body)

`GET/PUT /agents/{agent_id}/config` · `GET …/versions` (50 mais recentes) · `POST …/versions/{v}/activate` ·
`GET /agents/model-catalog`. Apps com papéis: `agent_config:read|manage` nas rotas. Service: get-or-default,
salvar = versão + snapshot em transação, invalida o memo (`tenant_instructions_cache_key`).

## Runtime

`tenant_instructions_middleware` lê `configurable.tenant_id` + `metadata.agent_id`, busca o Markdown (memo TTL)
e anexa DEPOIS do prompt base sob `## Instruções do negócio` (plataforma vence; prefixo cacheável). Sem
tenant/config/DB → prompt base puro. Quem chama precisa propagar `tenant_id`/`agent_id` no config (o
`streaming.py`/`executors.py` já fazem; job próprio: `UsageContext(...).runnable_config()` + `configurable`).
`agent_configs.model_id` hoje só alimenta a tela (catálogo de 1 modelo); 2º modelo entra no mesmo middleware
com `request.override(model=init_model_by_id(model_id))`.

## O que fica no APP, não no template

Dados do negócio injetados em runtime (horário, filas, catálogo), flags de captura (`sections`), `enabled`
on/off do atendente (nasce DESLIGADO; ligar exige canal conectado), preview/tester, regras de disclosure
(`integrations` → `meta-policy.md`), `org_agent_configs` legado do kailos/balizap até convergir.

## Catálogo de modelos

`model_catalog.py`: `ModelOption(config, label, description)`; `AGENT_MODELS` hoje = GLM 5.3 Flash (1 modelo
é a DECISÃO). `_validate()` quebra no import se um slug não existe no registry. Só modelos com credencial
configurada. Linha legada com outro slug → migration dbmate reescrevendo para `z-ai/glm-5.3-flash`
(precedente: balizap `20260909160000_default_model_glm_5_3_flash.sql`); `label_for()` mantém config antiga legível.

## Handoff humano

Tool `handoff_to_human` + equipes (`queues`: gatilhos, SLA, rodízio) moram no app e no gate `integrations`;
instruções do agente NÃO carregam a lista de equipes (vem da fila, injetada em runtime). Ao transferir:
estado `human_handling` + resumo (`streaming-backend.md` § Interrupção).
