---
name: integrations
description: PORTÃO obrigatório de integrações com plataformas externas de terceiros (hoje Meta — Facebook Login for Business, WhatsApp Business Cloud API, Instagram Graph; cresce com Stripe/Mercado Pago/etc no futuro). INVOCAR ANTES de criar/alterar QUALQUER integração — novo endpoint `/webhooks/meta/{deauthorize,data-deletion}` ou `/webhooks/whatsapp`, `FB.login`/Embedded Signup no frontend, exchange de `code` do Embedded Signup, validação HMAC de webhook (`signed_request`, `X-Hub-Signature-256`), gravação de `facebook_user_id` em `portal_connections`, popular `META_APP_SECRET`/`WHATSAPP_WEBHOOK_VERIFY_TOKEN` (.env) ou `meta_app_id`/`meta_es_config_id` (yaml). INVOCAR TAMBÉM para qualquer ENVIO de mensagem e política de plataforma — janela de serviço de 24h, template (criar/submeter/acompanhar aprovação/enviar), campanha ou disparo em massa, opt-in/opt-out de contato, quality rating e teto do número, preparar submissão ao App Review, ou mexer em prompt de agente de IA que fala com cliente final (disclosure). Checklist de invariantes (1 Meta App por SaaS, HMAC com `compare_digest`, webhook 200 em <10s, opt-in e janela de 24h, nada de segredo/assinatura em log) + roteia pras references profundas. NÃO confundir com o gate `auth` (login do usuário no SaaS) — aqui é integração SaaS↔plataforma externa.
---

# Integrations — O Portão (plataformas externas)

Ponto de entrada único de integração com terceiros. **NUNCA toque numa integração externa sem
passar por aqui.** Distinto do gate `auth` (que é login do usuário no SaaS): aqui o SaaS é cliente
de uma plataforma externa (Meta hoje). Os invariantes vivem nas references; a implementação completa
também.

## Checklist (em ordem; desça o que a tarefa exige)

- [ ] **1. Invariantes da plataforma** — 1 Meta App por SaaS, separação `.env` (2 secrets) vs yaml
  (públicos), tabela canônica de endpoints de webhook, regra 200<10s, `facebook_user_id` obrigatório,
  Don'ts → **`references/meta-invariants.md`** (leitura curta, sempre primeiro em trabalho Meta).
- [ ] **2. Implementação Meta** — runbook de código: Settings pydantic, WhatsApp client (exchange ES,
  get_facebook_user_id, subscribe, register), endpoint `/embedded-signup`, `decode_signed_request`,
  webhooks Deauth/Data-Deletion, `X-Hub-Signature-256`, botão `FB.login` no front, data-deletion page,
  smoke test, troubleshooting → **`references/meta-app-setup.md`**.
- [ ] **3. Política de plataforma** — janela de 24h, categorias de template, opt-in/opt-out, qualidade
  e teto do número, disclosure de IA, e o que a submissão ao App Review pode declarar. OBRIGATÓRIO em
  qualquer trabalho que envie mensagem, construa disparo/campanha, mexa em prompt de agente que fala
  com cliente final, ou prepare submissão → **`references/meta-policy.md`**.
- [ ] **4. Equipes (filas humanas) e handoff do agente** — schema de `queues` (descrição, gatilhos, prazo por
  fila), FK `assigned_queue_id`, tool `handoff_to_human(queue_name, …)`, bloco `## EQUIPES DE
  ATENDIMENTO` em runtime, SLA em horário comercial + rodízio, permissões `queue:*`, UI (texto visível diz "Equipes") →
  **`references/human-handoff-queues.md`**.

## Invariantes não negociáveis (sempre)

- **1 Meta App por SaaS** — NUNCA compartilhar entre produtos. Mesmo App em local/staging/prod (só URL muda).
- **2 secrets em `.env`**: `META_APP_SECRET` (HMAC das 3 surfaces) + `WHATSAPP_WEBHOOK_VERIFY_TOKEN`.
  NUNCA `WHATSAPP_APP_SECRET` separado. APP_ID/ES_CONFIG_ID/Graph version são **públicos** → yaml.
- Webhook **sempre** `200` em <10s (Meta faz retry indefinido); trabalho pesado → NATS JetStream (gate `infra`).
- HMAC **sempre** com `hmac.compare_digest` (timing-safe) — NUNCA `==`.
- **Gravar `facebook_user_id`** em `portal_connections.metadata_extra` no Embedded Signup — sem isso
  Deauth/Data-Deletion validam HMAC mas não acham a conexão.
- NUNCA logar `signed_request`/assinatura/body bruto em prod; NUNCA marcar Pages/Ads/Catalog/Pixel/IG como `required`.
- **Token de portal SEMPRE cifrado at rest** — nunca token vivo em coluna ou JSONB legível.
- **Origin de `postMessage`** (Embedded Signup) por **igualdade exata** contra allowlist — NUNCA
  `endsWith("facebook.com")`, que casa `evil-facebook.com`.
- **Embedded Signup é v4** — `extras: { setup: {} }` e nada mais. `sessionInfoVersion` (v2) ou
  `version: "v3"` no `extras` = versão descontinuada em **15/10/2026**; `feature:
  "whatsapp_embedded_signup"` nunca foi parâmetro documentado. Em v4 a variação do fluxo
  (coexistência, Marketing Messages, CTWA) é marcada na **Configuration**, não no código — o
  `config_id` é que decide. Detalhe e o que NÃO converte sozinho → `meta-app-setup.md`.

## Invariantes de política (quando o produto manda mensagem)

- **NUNCA** free-form fora da janela de 24h — fora dela, só template aprovado (a Graph recusa: `131047`).
- **NUNCA** mensagem business-initiated sem opt-in registrado com origem e evidência; flag nasce `false`.
- **NUNCA** guardrail de identidade do agente ANTES do texto configurável do tenant — é sobrescrevível.
- **NUNCA** declarar no App Review capacidade que existe no código mas não tem call site.
- Detalhe e o resto → `references/meta-policy.md`.

## References

- `references/meta-invariants.md` — invariantes Meta (App, secrets, endpoints, Don'ts) — antes era a rule always-on.
- `references/meta-app-setup.md` — runbook técnico completo (código backend + frontend, HMAC, troubleshooting).
- `references/meta-policy.md` — política de plataforma: janela 24h, categorias, opt-in/opt-out, qualidade do número, disclosure de IA, App Review.
- `references/human-handoff-queues.md` — equipes (filas humanas) e handoff do agente de IA (schema, tool, bloco de prompt, SLA/rodízio, API, UI; "Equipes" na tela, `queue` no código).
