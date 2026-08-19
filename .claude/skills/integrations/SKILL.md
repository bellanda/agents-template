---
name: integrations
description: PORTÃO obrigatório de integrações com plataformas externas de terceiros (hoje Meta — Facebook Login for Business, WhatsApp Business Cloud API, Instagram Graph; cresce com Stripe/Mercado Pago/etc no futuro). INVOCAR ANTES de criar/alterar QUALQUER integração — novo endpoint `/webhooks/meta/{deauthorize,data-deletion}` ou `/webhooks/whatsapp`, `FB.login`/Embedded Signup no frontend, exchange de `code` do Embedded Signup, validação HMAC de webhook (`signed_request`, `X-Hub-Signature-256`), gravação de `facebook_user_id` em `portal_connections`, popular `META_APP_SECRET`/`WHATSAPP_WEBHOOK_VERIFY_TOKEN` (.env) ou `meta_app_id`/`meta_es_config_id` (yaml). Checklist de invariantes + roteia pras references profundas. NUNCA 1 Meta App compartilhado entre SaaS; NUNCA `WHATSAPP_APP_SECRET` separado (é `META_APP_SECRET`); NUNCA APP_ID/ES_CONFIG_ID/Graph version em `.env` (são públicos → yaml); NUNCA validar HMAC com `==` (use `hmac.compare_digest`); NUNCA logar `signed_request`/`X-Hub-Signature-256`/body bruto; NUNCA webhook que responde >10s ou marca asset Meta como `required`. NÃO confundir com o gate `auth` (login do usuário no SaaS) — aqui é integração SaaS↔plataforma externa.
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

## Invariantes não negociáveis (sempre)

- **1 Meta App por SaaS** — NUNCA compartilhar entre produtos. Mesmo App em local/staging/prod (só URL muda).
- **2 secrets em `.env`**: `META_APP_SECRET` (HMAC das 3 surfaces) + `WHATSAPP_WEBHOOK_VERIFY_TOKEN`.
  NUNCA `WHATSAPP_APP_SECRET` separado. APP_ID/ES_CONFIG_ID/Graph version são **públicos** → yaml.
- Webhook **sempre** `200` em <10s (Meta faz retry indefinido); trabalho pesado → NATS JetStream (gate `infra`).
- HMAC **sempre** com `hmac.compare_digest` (timing-safe) — NUNCA `==`.
- **Gravar `facebook_user_id`** em `portal_connections.metadata_extra` no Embedded Signup — sem isso
  Deauth/Data-Deletion validam HMAC mas não acham a conexão.
- NUNCA logar `signed_request`/assinatura/body bruto em prod; NUNCA marcar Pages/Ads/Catalog/Pixel/IG como `required`.

## References

- `references/meta-invariants.md` — invariantes Meta (App, secrets, endpoints, Don'ts) — antes era a rule always-on.
- `references/meta-app-setup.md` — runbook técnico completo (código backend + frontend, HMAC, troubleshooting).
