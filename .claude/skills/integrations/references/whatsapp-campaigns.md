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
- Os dois caminhos de ingestão (`leads_poller.poll` da Loja Conectada e `site_leads.create_site_lead`)
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
  messaging_limit_tier`), cache 1h; sem leitura → assume **250/dia**.
- **Pausa automática:** qualidade RED (`quality_red`) ou rebaixamento/FLAGGED (`quality_yellow`),
  erro `131048` (limite de spam), >20% de falhas nos últimos 50 envios (mín. 10). Retomar dá 409
  com qualidade ≠ GREEN.
- Erro por destinatário (`131049`, número inválido, opt-out no meio) = `skipped`/`failed` naquele
  contato, sem pausar.
- **Parar** = `cancelled` (kill switch). Prévia (`/preview`) mostra "X serão enviados / Y pulados
  (motivo)" antes de iniciar.
- Permissão `whatsapp:campaign` (só admin por default).

## Pré-requisitos do lado da Meta (por app/WABA)

- `whatsapp_business_management` na Configuration do Embedded Signup.
- Webhook assinando `message_template_status_update`, `template_category_update`,
  `message_template_quality_update` e `phone_number_quality_update`.
- Confirmar contra a doc atual os campos `quality_rating`/`messaging_limit_tier` (alternativa:
  `whatsapp_business_manager_messaging_limit`).
