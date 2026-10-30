# WhatsApp — template automático por lead e disparo em massa (campanhas)

> Decisão do usuário (2026-10-14). Canônico = **kailos**. É feature de negócio do Kailos: NÃO
> propague para outros apps sem pedido — este arquivo existe para o próximo app que precisar
> copiar o desenho, não reinventar. Política de fundo (opt-in, opt-out, tier, qualidade) →
> `meta-policy.md`.

## Princípio

Todo envio business-initiated passa pelo MESMO `send_template` do envio individual
(`services/portals/whatsapp/whatsapp_template_service.py`) — automático, campanha e botão manual
herdam as mesmas travas (template APPROVED, opt-out vence, opt-in obrigatório para marketing, carro
exigido/sem preço). Nenhum caminho novo monta payload de template na mão.

## 1. Template automático na chegada do lead

- Config por org em `organizations.settings.lead_auto_template = {enabled, template_id}`; UI = card
  "Envio automático para novos leads" na seção `whatsapp-templates` do hub (ToggleCard + Select só
  com templates APPROVED; aviso quando o template pede carro).
- Os dois caminhos de ingestão (webhook da Loja Conectada `leads_webhook.ingest_lojaconectada_lead`,
  único desde 2026-10-29 — sem coleta periódica —, e `site_leads.create_site_lead`)
  publicam no NATS `whatsapp.tasks.lead_auto_template` **depois do commit**, por lead novo com
  contato. Falha de envio nunca derruba a ingestão.
- Envio "na hora, qualquer horário" (decisão do usuário).
- Pula (e grava o motivo): janela de 24h aberta (já está conversando), template recebido nos últimos
  **7 dias** (mesmo cliente em 3 portais), sem opt-in/opt-out. Dedup por lead com `SET NX` no Valkey
  (redelivery do JetStream).
- Rastro em `portal_leads.auto_template_status|reason|at` → chip na lista de leads.
- A IA atende a resposta já sabendo: `agent_dispatcher._active_message_block` traz template + carro +
  portal de origem + a mensagem que o lead escreveu no portal (lookup por `metadata.lead_id`).

## 2. Campanha (disparo em massa)

**Público:**
- Seleção na lista de leads (ação em lote) — cada lead leva o próprio carro de interesse.
- Planilha CSV/XLSX (nome, telefone, carro opcional; ≤5.000 linhas) → linhas revisáveis → commit.
  **Declaração obrigatória** do lojista ("estes contatos autorizaram…") + **origem** (texto livre,
  ex.: "leads do feirão de setembro"). Vira o opt-in de cada contato com `source=lead_list` e
  evidência "declarado por <usuário> em <data>: <origem>, campanha <id>". A CHECK da tabela trava a
  declaração no banco também. **Opt-out anterior nunca é sobrescrito**; opt-in já existente mantém
  origem/data (COALESCE).

**Schema:** `whatsapp_campaigns` (status `draft|running|paused|completed|cancelled`, `pause_reason`),
`whatsapp_campaign_recipients` (UNIQUE `(campaign_id, contact_id)`, `attempted_at` = claim antes do
envio → nunca reenvia, mesmo após crash), `whatsapp_campaign_imports`.

**Ritmo (o código decide):**
- Cron de 1 min publica `cron.whatsapp.campaign_tick`; consumer serial por org (trava Valkey).
- Lote = min(orçamento diário do tier − contatos únicos com template nas últimas 24h, teto por
  minuto). Tier + qualidade lidos da Graph (`GET /{phone_number_id}?fields=quality_rating,
  whatsapp_business_manager_messaging_limit,messaging_limit_tier`), cache 1h; sem leitura →
  assume **250/dia**. **O teto é do portfólio desde 2025-10-08**: o número devolve
  `whatsapp_business_manager_messaging_limit` (ex.: `TIER_2K`) e NÃO devolve mais
  `messaging_limit_tier` — ler só o campo antigo trava a campanha em 250/dia (kailos/Promocar,
  achado 2026-10-27). Prefira o campo novo, com o antigo de fallback.
- **Pausa automática:** qualidade RED (`quality_red`) ou rebaixamento/FLAGGED (`quality_yellow`),
  erro `131048` (limite de spam), >20% de falhas nos últimos 50 envios (mín. 10). Retomar dá 409
  com qualidade ≠ GREEN.
- Erro por destinatário (`131049`, número inválido, opt-out no meio) = `skipped`/`failed` naquele
  contato, sem pausar.
- **Parar** = `cancelled` (kill switch). Prévia (`/preview`) mostra "X serão enviados / Y pulados
  (motivo)" antes de iniciar.
- **Pulados em três blocos** na prévia (`skip-groups.ts` + `CampaignSkipBreakdown`, kailos e
  emporion, 2026-10-30): "Pediram para parar as promoções" (`opted_out`, com a garantia escrita:
  nunca recebem, nem com "Enviar para todos"), "Contato recente" (`recently_contacted` +
  `window_open`, que o "Enviar para todos" inclui) e "Outros motivos". O bloqueio é do backend em 3
  pontos (classificação na criação, `_blocking_reason` na prévia/envio avulso e re-leitura do contato
  no tick antes de cada lote); a tela só deixa visível. Reativação do opt-out → `meta-policy.md`
  §"Opt-out é obrigatório".
- Permissão `whatsapp:campaign` (só admin por default).

**Lotes programados + janela de envio + sugestão da IA** (decisão do usuário 2026-10-29; kailos
migration `20261029120000_whatsapp_campaign_pacing`; módulos `campaigns/pacing.py` (puro),
`batch_runner.py`, `pacing_suggestion.py`, `schedule_view.py`). Lista grande numa campanha só, em
vez de micro-campanhas à mão: menos risco de bloqueio e respostas espaçadas para o atendimento humano.
- **Sem scheduler novo.** O mesmo tick de 1 min; o "quando" é `whatsapp_campaigns.next_batch_at`
  no Postgres (sobrevive a deploy/restart do Valkey, aparece na tela). O cron só publica se há
  campanha `running` **vencida** (`next_batch_at IS NULL OR <= now()`); entre lotes custa zero.
- **Ritmo** = `batch_size` (1–1000; lote de 1 vale para teste, o mínimo 5 travou o 1º uso real
  em 2026-10-29) + `batch_interval_minutes` (5–1440), nulos juntos = modo
  contínuo (o de antes; campanhas antigas seguem nele). Lote conta ENVIOS (pulado não consome);
  teto diário do tier e pausas automáticas continuam por cima.
- **Janela própria da campanha** (`send_window_days VARCHAR(3)[]`, `send_window_start/end TIME`,
  nulas juntas = qualquer horário): fora dela nada sai e retoma no próximo dia marcado às `start`.
  Pré-preenchida do horário da loja (botão "Usar horário da loja"); a avaliação converte a janela no
  dict de `business_hours.py` e reusa `current_slot_end`/`next_business_opening`.
- **Grade:** próximo = `scheduled_at` do lote anterior + intervalo; se já passou (travou por
  teto/janela), agora + intervalo — dois lotes nunca colados. Depois alinha à janela. Retomar com a
  grade já vencida sai na hora. Início agendado = `running` + `next_batch_at` futuro + 0 lotes (sem
  status novo; até 30 dias).
- **Histórico:** `whatsapp_campaign_batches` (no máx. 1 aberto por UNIQUE parcial; contadores por
  GROUP BY nos destinatários, `recipients.batch_id` carimbado no claim) e `whatsapp_campaign_events`
  (`created|started|scheduled|paused|resumed|pacing_changed|completed|cancelled`, ator NULL =
  automático) gravado na MESMA instrução da transição (CTE) — estado e história nunca divergem.
- **IA sugere, código garante:** `POST /pacing-suggestion` junta fatos (teto e quanto resta hoje,
  qualidade, fila de outras campanhas, horário da loja, atendentes ativos, taxa de resposta 90 d —
  <50 envios = estimativa 15%) → Haiku `complete_structured` (prompt estático neutro, fatos em
  `<fatos>`) → código limita às faixas e calcula a projeção (a IA nunca calcula datas). Falha,
  timeout 20 s ou teto de gasto → heurística determinística (`source: "calculated"`). A rota usa
  `Depends(get_conn_scope)` (escopo por fase), nunca `get_conn` segurando conexão durante o LLM.
- **Pedido livre do lojista** (`notes` ≤1000, campo "O que a IA deve saber sobre o envio?" já na
  etapa dos dados e reeditável no passo Ritmo/"Alterar ritmo"; pedido do usuário 2026-10-29): vai
  delimitado em `<pedido_da_empresa>` no FIM do prompt e **vence os critérios de conforto** (teste
  "5 a cada 10 min agora", "fechar o mês até sábado"), nunca o teto diário nem as faixas. Os fatos
  levam `agora` (dia da semana + data/hora no fuso da loja) para prazos. Intervalo da IA = múltiplo
  de 5 em 5–1440 (os atalhos da tela são só atalhos). Sem IA, a sugestão calculada avisa na
  explicação que o pedido não entrou. O pedido entra na query key do front (texto novo = sugestão nova).
- **Projeção** (`POST /pacing-projection`, puro, front chama com debounce 300 ms): lotes previstos,
  término, `daily_limit_warning` quando o acumulado de 24 h (ou um lote sozinho) passa do teto.
  O `enabled` da query entra NO MESMO debounce do input: ligado na hora com input atrasado, o
  front postava o valor inválido anterior (422 + toast; kailos 2026-10-29). Erro fica inline
  (`meta.silentError`).
- **Tela:** criação em passos no mesmo `FormDialog` (… → Ritmo com carregamento + checklist dos fatos
  → sugestão editável → Prévia com "Iniciar agora"/"Agendar início"); detalhe com linha de estado
  viva + UMA linha do tempo com divisor "Agora" (ocorreu: eventos + lotes; em andamento; vai ocorrer:
  próximos lotes esmaecidos), lote clicável filtra os destinatários (`?batch=n`), "Alterar ritmo".

**"Enviar para todos"** (decisão do usuário 2026-10-15; migration `20261015121000_whatsapp_campaign_send_all_and_fallback`, colunas `ignore_recent_activity` e `fallback_template_id`, mais `whatsapp_campaign_recipients.template_id` e novos `skip_reason`):
- Caixa opcional, desmarcada por padrão. Fica persistida em `whatsapp_campaigns.ignore_recent_activity`.
- Ligada, a campanha ignora as duas regras dinâmicas na criação, na prévia e no tick: template
  recebido há menos de 7 dias e janela aberta.
- **Opt-out e as travas de `_blocking_reason` continuam bloqueando sempre.**
- O template automático por lead não muda.

**Placa por linha da planilha** (decisão do usuário 2026-10-15; REGRA DE NEGÓCIO do kailos — só o mecanismo de *template de reserva por destinatário* é reutilizável em outro app):
- **Formato:** dígitos = id do carro. Fora isso, só vale placa de 7 caracteres, ou de 8 com `-` na 4ª
  posição. A placa é normalizada sem hífen e precisa casar o padrão antigo ou o Mercosul.
- **Carro utilizável** = `em_estoque` + foto de capa. A checagem vive num ponto só e vale para:
  - o carro da linha;
  - o carro da campanha;
  - o carro do lead;
  - a revalidação no tick (o carro pode ter sido vendido entre a planilha e o envio).
- **Precedência:** a linha vence. O carro da campanha só cobre célula vazia. Placa ruim nunca cai
  no carro da campanha, porque mandaria o carro errado.
- **Revisão:** cada linha com problema mostra o motivo: formato inválido, placa não encontrada, fora
  de estoque ou sem capa. Problema de carro **não** invalida a linha.
- **Template de reserva:** `fallback_template_id`, APPROVED e sem exigir carro (o de loja).
  - Linhas sem carro utilizável recebem esse template (`whatsapp_campaign_recipients.template_id`).
  - Sem reserva, essas linhas são puladas com o motivo.
- **Telefone repetido:** a primeira linha vence; as outras aparecem com `duplicate_of_row`.

**Resposta ao botão do template:**
- Chega como `type:"button"` e precisa estar no CHECK de `whatsapp_messages.message_type`; ver
  `meta-invariants.md`.
- A IA usa o template **respondido**: `replied_to_wa_id` do `button` → template enviado, mais o carro
  do payload `tpl_interest:<template>:<carro>`. Só se não achar, usa o último template enviado.
- O roteamento não muda: conversa ativa com vendedor vai para ele; senão, IA.
- O que a resposta SIGNIFICA vem do template, nunca de nota fixa no código: ver §3b.

**O que a IA de atendimento deve saber** (`whatsapp_campaigns.attendant_brief`, ≤1000, editável
depois de criada): contexto da campanha escrito pela loja (data/horário do evento, condição). Vai
truncado e entre aspas no bloco "MENSAGEM ATIVA". NÃO confundir com o "pedido livre" do ritmo, que só
orienta a sugestão de lotes.

## 3. Templates — criar, sincronizar e enviar (kailos `services/portals/whatsapp/`)

Fonte da verdade do status é a Meta; o banco (`whatsapp_templates`) é espelho. Envio só com `APPROVED`.

**Criar / submeter** (`whatsapp_template_service.py`: `submit_suggested_template`, `create_custom_template`,
`_submit_to_meta`)
- Categoria fixa `MARKETING`, idioma `pt_BR`, variáveis **nomeadas** (`parameter_format: NAMED`, só quando o
  corpo tem variável). Nome único por org+idioma (409 antes de ir à Meta). Texto aprovado é imutável: mudar
  uma vírgula = template novo (`_v1` → `_v2`; `template_catalog.py` guarda as sugestões como constantes).
- **Cabeçalho de imagem exige exemplo**: `_upload_header_example` → `wa_client.upload_template_header_example`
  (Resumable Upload API em 2 passos: abre sessão `POST /{app_id}/uploads?file_length&file_type`, depois
  `POST /{session_id}` com os bytes, header `Authorization: OAuth <token>` — **não** `Bearer` — e
  `file_offset: 0`; devolve o handle `h` que vai em `components[0].example.header_handle`). Usa `meta_app_id`
  do yaml (`vite.meta_app_id`).
- **Mídia do header** (`template_media.py`): a Meta só aceita JPEG/PNG e busca a URL SEM autenticação; o app
  guarda AVIF. Cada foto de origem vira UM derivado JPEG (≤1600px, `org_uploads` `whatsapp_media`,
  `entity_type=whatsapp_template_header`) reaproveitado em todo envio. Fonte do header é enum fechado
  (`vehicle.cover_photo` | `org.banner`); sem foto → 400 pt-BR.
- **Variáveis** (`template_variables.py`): cada variável tem uma *fonte* de enum fechado (`contact.first_name`,
  `org.name`, `vehicle.label`, `vehicle.price`, `manual`) guardada em `variable_bindings`; no envio só mudam
  (1) valores das variáveis, (2) imagem do header, (3) sufixo do botão de URL. Payload dos quick replies:
  `tpl_interest:<template_id>:<carro|->` e `tpl_opt_out`.
- **Validação server-side antes da Meta** (`template_validation.py::validate_custom_template`): a Meta recusa
  em inglês e após round-trip, então barramos o que dá: nome `[a-z0-9_]`, corpo ≤1024 sem começar/terminar
  em variável, variáveis usadas == declaradas e cada uma com exemplo, header de texto ≤60 sem variável,
  rodapé ≤60, botão ≤25 chars, ≤10 botões, ≤2 de URL (https, `{{1}}` só no fim do link). Todo erro é 400
  pt-BR. Marketing leva sempre o quick reply "Parar promoções" (`OPT_OUT_BUTTON_TEXT`).
- Erro síncrono da Graph vira `MetaGraphError(code, subcode, msg)`; `translate_meta_error` → pt-BR.

**Sincronizar** (`sync_templates_from_meta`, `client.list_message_templates`): segue `paging.next` até
acabar, com `TEMPLATES_PAGE_LIMIT = 100` por página e teto `TEMPLATES_MAX_PAGES = 50` (protege de cursor que
não avança); `TEMPLATE_FIELDS` pede `id,name,language,category,status,components,parameter_format,
rejected_reason,quality_score`. Template apagado na Meta (`_is_gone_on_meta`) é tolerado no delete local.

**Webhook de template** (`template_webhook.py`; `entry[].id` = **WABA**, não o `phone_number_id` das
mensagens): `message_template_status_update` (`event` → status via `STATUS_BY_EVENT`; `FLAGGED` não muda
status; evento desconhecido é logado e ignorado, nunca gravado — o CHECK negaria),
`template_category_update` (`new_category`) e `message_template_quality_update` (`new_quality_score`).
Template criado fora do app só é logado; o próximo `sync` o traz. Os três campos precisam estar com
Subscribe no painel da Meta (commit `1def2ad`).

**Envio** (`evaluate_template` → `_blocking_reason` → `dispatch_evaluated_template`; `send_template` é o
wrapper do envio avulso). Travas, nesta ordem: `not_approved`, `reply_actions_missing` (§3b), `opted_out`, `no_opt_in`, `vehicle_required`,
`vehicle_without_price`, `missing_value` (variável vazia ou header sem foto). `dispatch_evaluated_template`
deixa `MetaGraphError` subir CRU: o envio avulso traduz para o usuário, a campanha precisa do `code` para
decidir entre pular o contato e pausar. `sender_kind` ≠ `human` para envio de sistema não contar como
resposta de vendedor nas métricas.

## 3b. Comportamento por resposta rápida (`reply_actions`, kailos 33f6758 + emporion, 2026-10-30)

Incidente que originou (kailos prod 2026-10-29): todo quick reply virava `tpl_interest` + uma nota
fixa "aceitou conversar, qualifique", e "Já comprei meu veículo" foi atendido como pós-venda, com
follow-up no dia seguinte. Decisão do usuário: a LOJA define, por botão, o que acontece.

- **Onde mora:** `whatsapp_templates.reply_actions` JSONB, uma entrada por quick reply
  `{button_text, action, instruction, message, queue_id}`; nunca vai à Meta, editável após aprovado
  (`PATCH /whatsapp/templates/{id}/reply-actions`, valida texto do botão, campos por ação e equipe da org).
- **Ações:** `ai` (IA atende; `instruction` opcional da loja), `close` (manda `message` fixa em texto
  livre, sem IA e sem follow-up), `record` (só registra), `handoff` (transfere para `queue_id` pelo
  mesmo caminho do `handoff_to_human`), `opt_out` (derivado sozinho para "Parar promoções", texto
  normalizado `parar promocoes`).
- **Trava de envio:** quick reply sem entrada = `missing_reply_actions` → `_blocking_reason`
  devolve `reply_actions_missing` logo depois de `not_approved` (avulso 409, criar campanha 409,
  destinatário pulado, lead automático bloqueado). O front mostra o editor INLINE no próprio diálogo
  de envio/campanha (`MissingReplyActionsGate`) — template criado direto na Meta e trazido pelo sync
  cai aqui. Migration faz backfill: opt-out → `opt_out`; kinds de sistema → `ai`; `custom` fica só
  com o opt-out (a loja preenche o resto).
- **Registro:** `whatsapp_template_replies` (uma linha por resposta, `UNIQUE(inbound_message_id)` =
  redelivery não reaplica; `source` tap | text | ai; liga ao destinatário pela `wa_message_id` do
  template respondido). Casamento: toque (`context.id`) ou texto igual ao botão nos últimos 7 dias.
- **Webhook** (`template_reply.process_inbound_reply`, ANTES do opt-out): `handled=True` = não
  dispara a IA. `opt_out` NUNCA é `handled` (o descadastro segue no fluxo, inclusive com humano na
  conversa — bug pego na revisão de 2026-10-30). Conversa com humano: só registra.
- **IA:** o bloco "MENSAGEM ATIVA" lista cada botão e o comportamento (+ `attendant_brief`); se o
  cliente ESCREVE o equivalente, a tool `record_template_reply(button_text)` registra e devolve o que
  fazer (opt_out escrito descadastra de verdade).
- **Follow-up:** gate `template_reply_closed` quando a última mensagem recebida foi resposta
  `close`/`record`/`opt_out`; mensagem nova do cliente libera sozinho.
- **Leitura:** `reply_summary` no detalhe da campanha (contagem por botão + sem resposta), filtro
  `reply=<texto|__none__>` nos destinatários e filtro do inbox por campanha/resposta
  (`GET /whatsapp/conversations?campaign_id=&campaign_reply=`, exige permissão de campanha; ref
  `frontend` → `whatsapp-inbox.md`).

## 4. Erros da Meta → motivo em pt-BR (`meta_errors.py`, folha sem imports de serviço)

Dois caminhos, mesma tabela `META_ERROR_MESSAGES` (code → texto): (a) erro síncrono da Graph no envio;
(b) `statuses[].errors` do webhook, que chega DEPOIS do 200 do envio (a Meta aceita e só então vira
`failed` — ex.: `131042` conta sem moeda/pagamento, visto em prod 2026-10-14 com "enviado" na tela e nada
entregue). `describe_webhook_status_errors` grava `error.reason` na mensagem; o front mostra
(`failureReason()` → `whatsapp-inbox.md`). Código fora da tabela cai em "A Meta não entregou: <detalhe>".
Códigos cobertos: 132000/132001/132012/132015/132016 (template), 131049 (limite de marketing por cliente),
131026 (sem WhatsApp), 131047 (janela 24h), 131042 (faturamento), 131031, 131050 (opt-out na Meta), 131048
(spam), 131056, 130429, 131051, 131053, 368, 2, 190 (token expirado → reconectar).
`META_ACCOUNT_LEVEL_CODES = {131042, 131031, 368}` falham TODO envio da WABA até alguém corrigir fora do
app: campanha para em vez de queimar um destinatário por tick.

## 5. Falhas na campanha — pular, parar ou esperar (`campaigns/tick.py::_handle_meta_error`)

Nunca há reenvio automático de destinatário `failed`: `attempted_at` é reivindicado antes da Graph e
`fail_stale_claims` marca `failed` o que ficou >10 min reivindicado sem resultado ("não repetido para não
duplicar"). O que existe é **devolver a vez** (`release_claim`, o destinatário volta à fila):
- `131048` (spam) → devolve + pausa `spam_rate_limit`; códigos de campanha/conexão (`190`, `132000/1/15/16`
  + `META_ACCOUNT_LEVEL_CODES`) → devolve + pausa (`failure_rate`); retomar reenvia esses destinatários.
- `130429` (throughput) → devolve e espera o próximo tick, sem pausar.
- `131049`/`131026` (`META_RECIPIENT_SKIP_CODES`) → `skipped` com `meta_rejected` + motivo pt-BR, sem pausar.
- Qualquer outro erro → `failed` com `translate_meta_error`; taxa >20% em 50 envios (mín. 10) pausa.
- O reenvio **manual** de mensagem avulsa que falhou é do inbox (`ResendFailedMessage`), não da campanha.
- Lote: `CAMPAIGN_MAX_PER_TICK = 60`, `CAMPAIGN_MAX_PROCESSED_PER_TICK = 300`, até 8 lojas em paralelo.

## Pré-requisitos do lado da Meta (por app/WABA)

- `whatsapp_business_management` na Configuration do Embedded Signup.
- Webhook assinando `message_template_status_update`, `template_category_update`,
  `message_template_quality_update` e `phone_number_quality_update`.
- Teto: `whatsapp_business_manager_messaging_limit` (portfólio, confirmado em prod 2026-10-27);
  `messaging_limit_tier` ficou só como fallback de leitura.
