# Modelos, custo por tenant, history window e prompt cache

> Reference do gate `ai-agents`. Canônico: `core/agents/{models,custom_providers,callbacks,history_window,prompt_cache}.py`,
> `repositories/agents/usage.py`, AGENTS_SUBSYSTEM.md §2, §7, §10.

## Registry de modelos

`ModelConfig` frozen em `models.py` (`Models.<Provider>.<NAME>`): `model_id`, `provider`, `reasoning`,
`reasoning_effort`, preços (`input/cached_input/output_per_1m`), `supports_{image,pdf,audio,video}_input`,
`provider_order`, `allow_provider_fallbacks`. Instancie só por `init_model(cfg, **overrides)` /
`init_model_by_id(id)` (`custom_providers.py`; `ChatOpenRouter` = `langchain-openai` no base URL do OpenRouter,
reasoning + custo real). Um `match config.provider` é o único ponto que conhece SDKs.

- Claude Haiku 5.5 (`anthropic/claude-haiku-5.5`): 0.10 in / 0.01 cache read / 0.125 cache write / 0.50 out por 1M;
  `reasoning_effort="low"` (maiores são lentos demais p/ WhatsApp: medium p90 12s, xhigh p90 28s, max p50 79s);
  upstreams EUA `("anthropic", "amazon-bedrock/us-east-1", "google-vertex/us")` com `allow_provider_fallbacks=False`
  = **decisão de jurisdição** (declarada à Meta/privacidade), não de preço. Não relaxe. Tokenizer ~1,6x mais
  tokens que o GLM p/ o mesmo texto. Bake-off 2026-10-10: ≈ metade do custo do GLM high, 6–9x menos fatos inventados.
- **Timeout + retries explícitos** (`custom_providers.py`): `OPENROUTER_REQUEST_TIMEOUT_SECONDS=45`, `OPENROUTER_MAX_RETRIES=1` via `kwargs.setdefault` (caller ainda sobrescreve). Sem isso valem os defaults do SDK OpenAI (600s + 2 retries): um stream travado segurou a trava da conversa do WhatsApp até o TTL (180s) sem um log — cliente esperou 3 min (kailos prod, 2026-10-16). Todo turno de agente disparado por webhook leva ainda um TETO (`anyio.fail_after(AGENT_TURN_MAX_SECONDS)`, abaixo do TTL da trava): estourou → log `agent_turn_timed_out`, na última entrega a conversa vai a um humano (`reason="agent_turn_timeout"`), e o release da trava roda em `CancelScope(shield=True)`.
- Whisper: preço por HORA (0.04), não passa por `init_model`.
- **Modelo sem preço no registry lê custo ZERO em silêncio.** Todo modelo novo nasce com preço.
- Modelo novo só se a rule `ai-agents.md` mudar (`propagation.md`).

## Custo

- `UsageRecorderCallback` (global, anexado no registry e via `UsageContext.runnable_config()` em modelo nu):
  `on_chat_model_start` guarda metadata por `run_id`; `on_llm_end` insere 1 linha em `agent_message_usage`
  (`thread_id, message_id, user_id, client_id, agent_id, tenant_id, provider, model_id, input/cached/output/
  reasoning/total_tokens, cost_usd, error, created_at` — imutável). Sem `thread_id`+`agent_id` no metadata a
  linha é descartada.
- `compute_cost_usd`: `(fresh·in + cached·cached_in + out·out)/1e6`, `fresh = input − cache_read`, arredonda
  PARA CIMA (`round_cost_up`). **Custo reportado vence a tabela:** `ChatOpenRouter` expõe
  `response_metadata["provider_cost_usd"]` (+ `upstream_provider`) e `build_usage_from_ai_message` o prefere.
  **BYOK** (chave Anthropic própria cadastrada no OpenRouter, decisão 2026-10-19 — créditos do Max 20x):
  com `usage.is_byok`, `usage.cost` é só a taxa do OpenRouter (0 na franquia) e a inferência vem em
  `usage.cost_details.upstream_inference_cost`; o stamp SOMA os dois. Ler só `usage.cost` zera o custo
  de todo tenant e o teto de gasto. Teste: `tests/agents/test_openrouter_cost.py`.
- Agregações (`repositories/agents/usage.py`): `get_thread_total_cost_usd`, `get_user_total_cost_usd`,
  `get_tenant_cost_usd_since(conn, tenant_id, month_start_utc())` — base de qualquer teto de gasto por tenant
  (índice parcial `(tenant_id, created_at)`). kailos/emporion mapeiam `organization_id` → `tenant_id`.
- One-shot: `LlmResult.cost_usd` + `cost_is_real` para creditar o teto assim que a chamada volta.
- Checagem de teto: antes de fluxo caro (`spent + estimate > cap`) → recuse com mensagem clara ao usuário;
  a política do teto (valor, plano) é do app, a medição é do template.
- Dimensões: `agent_id` (propósito; subagente `:<nome>`), `tenant_id`, `thread_id`, `model_id`. Planeje os
  `agent_id` antes — mudar depois quebra a série histórica.

## History window

`sliding_window_middleware` (`history_window.py`): mantém o turno atual intacto; do mais recente ao mais
antigo substitui `ToolMessage` pesado por placeholder até `MAX_MESSAGES_TO_LLM=80` / `MAX_TOKENS_HEURISTIC=256k`
(÷4); remove `ToolMessage` órfão no início (quebra o provedor). Só o que o MODELO vê é cortado — checkpoint
e UI guardam tudo. Todo agente de chat leva o middleware, primeiro da lista.

## Prompt cache

- **Do provedor** (OpenRouter/Haiku): NÃO é implícito — só com `cache_control: {type: ephemeral}` no topo do body
  (flag `prompt_cache_control=True` no `ModelConfig`, aplicada pelo `init_model`). Leitura = 10% do preço, escrita = 125%;
  aparece em `cache_read`, cobrado em `cached_input_price_per_1m`. Exigência: prefixo estável — prompt base estático → instruções do tenant
  → dado dinâmico; nada de timestamp/request id/UUID no topo; mesma ordem de tools.
- **`prompt_cache.py`**: memo TTL in-process (`settings.agents.tenant_config_ttl_seconds`, 30 s) das instruções
  do tenant — o middleware roda antes de CADA chamada de modelo (loop de tool = várias). Salvar pela API
  invalida o worker que atendeu; os demais convergem no TTL. Cross-worker estrito → Valkey (gate `infra`).

## Schema

`agent_message_usage`, `chat_history`, `checkpoints*`, `user_uploads` na migration inicial;
`agent_message_usage.tenant_id`, `agent_configs`, `agent_config_versions` em `20260930120000_tenant_agent_configs.sql`
(dbmate; gate `database`). `db/schema.sql` é dump, nunca editado à mão.
