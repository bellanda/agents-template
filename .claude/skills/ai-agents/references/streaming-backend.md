# Chat com streaming (backend)

> Reference do gate `ai-agents`. Canônico: `backend/src/api/routes/agents/{chat,threads,models}.py`,
> `services/agents/{streaming,executors,registry}.py`, `services/auth.py`, AGENTS_SUBSYSTEM.md §4–§6, §9, §12.

## Endpoints

| Rota | Função |
| --- | --- |
| `POST /agents/chat/completions` | one-shot (`stream=false`, JSON OpenAI-like) ou chat contínuo (`stream=true`, SSE). `thread_id = session_id` (gerado se ausente) |
| `GET/DELETE /agents/threads`, `GET /agents/threads/{id}` | histórico (`chat_history`), owner-scoped (403 se outro dono); DELETE também limpa uploads da thread |
| `GET /agents` | lista agentes + `capabilities` (front monta o picker e o `accept=`) |
| `GET /agents/model-catalog` | modelos escolhíveis (label + preço) |

## Identidade: seam única

Toda rota de chat/threads/uploads faz `ctx = Depends(get_auth_context)` →
`{"user_id","client_id","tenant_id","roles"}`. **`user_id`/`tenant_id` NUNCA do body.** Trocar auth =
trocar `resolve_identity` (verificação JWT real, `AuthenticationError`). `tenant_id` = `organization_id`
do token nos apps (no template = `user_id`). Fluem para `configurable.tenant_id` (middleware de
instruções), metadata do `usage_recorder` e `chat_history`. Rotas de gestão usam permissões do app
(`agent_config:read|manage`). Detalhes de auth → gate `auth`.

## Protocolo SSE (Vercel AI SDK v5)

`StreamingResponse(media_type="text/event-stream")`, 1 JSON por evento:
`start` → `text-start|delta|end` · `reasoning-start|delta|end` · `tool-input-available` ·
`tool-output-available` · `tool-output-error` · `error` · `finish`.

- Reasoning vem de `content[]` e de `additional_kwargs["reasoning_content"]` → `reasoning-delta`.
- Eventos com `SUBAGENT_RUN_TAG` são descartados (`subagents.md`).
- Saída de tool `{"type","data"}` é o envelope que o front transforma em card (`frontend-chat.md`).
- O último `AIMessage.usage_metadata` é capturado para gravar `usage` no `chat_history` da mensagem assistant.

## Interrupção e persistência

- Cliente cancelou → `CancelledError` capturado, marcador `_Interrompido pelo usuário._` e **save destacado**
  (`_spawn_detached`) que sobrevive ao cancelamento: turno parcial em `chat_history` (upsert `ON CONFLICT`).
- Checkpoint já persistiu o estado do grafo a cada passo — recuperável se o cliente cair.
- WhatsApp: desligar agente/handoff → `transition(state="human_handling")` + evento + `handoff_summary`
  (`integrations` → `human-handoff-queues.md`). Debounce/superseded via Valkey (gate `infra`).

### WhatsApp — turno descartável (kailos 2026-10-14, decisão do usuário)

Debounce de entrada (5 s de silêncio, estado `last_id`/`last_at` no Valkey, trigger antigo =
superseded) junta a rajada ANTES de o agente começar. Mensagem que chega DURANTE a geração tem regra
própria — **interrompe, descarta e responde ao conjunto** (1 + 2 + …), nunca responde à 1 por cima da 2:

- **Watcher** (`agent_turn_runner.run_discardable_agent_turn`): task group com o `ainvoke` + um loop
  que relê o debounce a cada 0,5 s; `last_id` ≠ trigger → cancela o scope. Valkey fora no watcher =
  segue (fail-open; a entrada já é fail-closed). Reconfere uma vez depois do `ainvoke`. Exceção do
  agente sai do task group como veio (guardada e relançada, sem `ExceptionGroup`).
- **Limite = primeira ação visível**: tool com efeito (enviar fotos/documento, transferir) chama
  `claim_turn_side_effect(config)` ANTES de qualquer `await` (`AgentTurnGuard` em
  `configurable["turn_guard"]`; marcar/cancelar e reservar/agir são síncronos, sem corrida no event
  loop). Já agiu → o turno não é mais descartado (desfazer faria o agente esquecer o que mandou).
- **Descartar = desfazer**: `checkpointer.alatest_checkpoint_id(thread)` antes do turno e
  `arollback_thread(thread, keep_through)` no descarte (apaga `checkpoints`/`checkpoint_writes` com
  id maior; uuid6 ordena como texto). `last_agent_trigger_at` NÃO anda.
- **Fila por conversa, nunca entre conversas** (usuário 2026-10-14): o consumer do agente NÃO
  processa o lote em sequência (`for msg: await handle`) — isso fazia uma conversa esperar atrás de
  outras do mesmo lote. Cada trigger vira uma task (`anyio.Semaphore(MAX_CONCURRENT_TURNS_PER_WORKER)`,
  8; o `fetch` só pede o que cabe nas vagas livres, o resto fica no stream para outro worker) com
  heartbeat `msg.in_progress()` a cada 20 s (espera + geração pode passar do `ack_wait` e o JetStream
  reentregaria o mesmo trigger). A MESMA conversa é serializada entre workers por trava no Valkey
  (`SET NX EX 180` com token, solta por Lua CAS; espera até 30 s, depois NAK). Erro do handler sai do
  task group guardado e relançado (senão `ExceptionGroup` não casa com os `except` de supersede/debounce).
- **`last_agent_trigger_at` = `created_at` da última inbound LIDA no turno**, nunca `NOW()` do envio:
  com `NOW()` a mensagem que chegou durante a geração ficava antes do carimbo e sumia do turno seguinte.

### WhatsApp — tempo, sessão, guard de transferência e follow-up (prod 2026-10-19)

Tudo abaixo é texto montado SEM LLM, no dispatcher/serviço (não no prompt do agente).

- **Carimbo por mensagem:** toda linha que o agente/follow-up vê (cliente, IA, vendedor) leva
  `[seg 19/10 08:55]` (hora local da loja). Sem isso "vou amanhã" dito no domingo era lido na
  segunda como ainda "amanhã". Um único formatador (`message_clock`) para todos os caminhos.
- **"Agora: seg 19/10/2026 08:55 (horário de Brasília)" vai no FIM do `user_text`, NUNCA no system
  prompt:** o prompt tem que ficar byte-estável por org para o prompt cache.
- **Separador de retomada:** pausa >= 4 h (ou outro dia local) injeta "retomou após …" antes da
  mensagem nova.
- **Sessão nova após lacuna >= 8 h:** novo `thread_id` (checkpoint limpo); o antigo vai para
  `metadata.previous_thread_ids`; `session_started_at` evita rotacionar duas vezes na rajada. O
  turno novo recebe um bloco curto `## CONVERSA ANTERIOR` (últimas falas do cliente + falas do
  vendedor, truncadas, gerado sem LLM) e a tool `read_conversation_history(days_back)` traz o
  histórico completo só se o modelo precisar (default 7 d, teto 90, ~40 msgs). Decisão do usuário.
- **Falas do vendedor** escritas durante o atendimento humano entram no contexto (`[Vendedor …]`);
  o checkpoint do agente só guarda o que ele próprio viu.
- **Trigger com `pending` vazio não invoca o agente** (nada novo do cliente = nada a responder).
- **Erro pós-efeito-colateral avança o marcador do trigger** (`last_agent_trigger_at`): se fotos/
  transferência já saíram e depois algo lançou, reentregar repetiria o efeito.
- **Guard de anúncio de transferência sem a tool:** o modelo escreveu "passei pro consultor" sem
  chamar `handoff_to_human` → o CÓDIGO completa o handoff (não reescreve a msg, o cliente já leu),
  com resumo forçado. Regex de verbo + papel (consultor/vendedor/atendente); pergunta ("posso te
  passar…?") e oferta condicional ("Se quiser, vou te passar…" — `se/caso/quando` antes do verbo na
  mesma frase) NÃO contam. Turno que transferiu mas veio sem texto manda frase fixa.
- **Botão de template "Quero atendimento" != pedido de humano:** é resposta de interesse; quem
  decide a transferência é o agente.
- **Follow-up da IA** (`agent_followup_schedule`, funções puras com `now` injetado): 20 min / 3 h /
  22 h contados da última resposta da IA. Passo 1 só se a resposta está `read` (e o cliente quieto
  >= 20 min) ou `delivered` há > 2 h; 1 ciclo por dia local por conversa (inbound novo reinicia o
  relógio mas não o passo 1 se já houve follow-up hoje); sem menu/lista; guard de estilo no texto
  gerado com 1 regeneração (limite por passo, 2026-10-30: passos 2–3 entregam oferta + diferencial
  da config da loja + pergunta de escolha, ver `integrations` → `human-handoff-queues.md`); só em horário da loja (adia, ou pula se a janela de 24 h fecharia); tick
  deduplicado por minuto entre workers (`SET NX` do minuto, fail-open).
- **SLA pós-handoff da IA:** conversa entregue pela IA sem fala de vendedor desde o handoff entra no
  rodízio; o relógio começa no EVENTO de handoff (a despedida da IA outbound escondia cliente
  quieto). Só sem resposta humana depois; janela de 48 h no evento para o 1º deploy não girar o
  histórico antigo inteiro. Cron e `sla_deadline` (contador do header) mudam juntos.

## Mensagem do usuário (multimodal)

`_extract_user_content` (`chat.py`): imagem → parte `image_url` inline (400 se `supports_image_input`
falso); documento/áudio/vídeo → MarkItDown extrai texto. Imagem chegando em modelo que não aceita = 400
ANTES de gastar request. Detalhes e uploads → `media-ocr.md`.

## Wiring (main.py)

`setup_logging()` antes do app; lifespan: `init_asyncpg_pool` → `init_checkpointer` →
`reload_agents_registry`; shutdown inverso. `LoggingMiddleware`; router de agents sob `api_router`;
`StaticFiles` de uploads montado DEPOIS do router. Config yaml: `agents:` (`stream_debug`,
`max_concurrent_llm`, `llm_max_retries`, `tenant_config_ttl_seconds`) + `openrouter:` nos 3 `config/app/*.yaml`
(skill `python-config-bootstrap`).
