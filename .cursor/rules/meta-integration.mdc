# Meta Integration

Invariantes operacionais para qualquer projeto que integre com Meta (Facebook Login, WhatsApp Cloud API, Instagram Graph). Pareado com a skill `meta-app-setup` (runbook completo + snippets) e a reference `references/meta/meta-app-setup.md` (passo-a-passo dashboard Meta).

## App Meta — 1 por SaaS

- **Cada SaaS = 1 Meta App próprio.** NUNCA compartilhe entre produtos. Hierarquia: 1 BM → N Meta Apps. Display Name aparece no popup pro cliente final; rate limits, App Review, Privacy Policy URL são por App.
- **O mesmo App roda local/staging/prod.** Só URLs/domínios mudam por env (App Domains, OAuth Redirects, webhook callbacks).

## `.env` — 2 secrets, só

```bash
META_APP_SECRET=                  # App Secret do dashboard Meta
WHATSAPP_WEBHOOK_VERIFY_TOKEN=    # string aleatória que VOCÊ escolhe, cola também na Meta
```

- `META_APP_SECRET` valida HMAC de **3 coisas distintas**: `X-Hub-Signature-256` (msgs WhatsApp), `signed_request` (Deauth/Data Deletion), exchange do Embedded Signup. **NÃO duplique** em `WHATSAPP_APP_SECRET` ou outras vars — é o mesmo valor.
- Verify token: gere com `uv run python -c "import secrets; print(secrets.token_urlsafe(32))"`. Pode diferir entre envs por boa prática.

## `config/app/{env}.yaml` — público, versionado

```yaml
whatsapp:
  public_base_url: https://dev-tunnel.bellanda.app    # local
                   https://<projeto>-temporario.bellanda.app   # staging
                   https://<projeto>.com.br                    # prod
  # abuse limits...

vite:
  meta_app_id: "<App ID>"           # numérico do dashboard
  meta_es_config_id: "<Config ID>"  # do Facebook Login for Business → Configuration
  meta_graph_api_version: v25.0
```

- App ID, ES Config ID, Graph version são **PÚBLICOS** (aparecem no JS bundle quando o SDK FB inicializa). Vivem em yaml, NÃO em `.env`.
- `public_base_url` em `whatsapp:` é a URL HTTPS que a Meta usa para webhooks e que o backend usa em media links (`send_document_link`).

## Endpoints de webhook — naming canônico

| Webhook | Path | Validação |
|---|---|---|
| WhatsApp messages | `/api/v1/webhooks/whatsapp` | `X-Hub-Signature-256` HMAC com `META_APP_SECRET` |
| Deauthorize | `/api/v1/webhooks/meta/deauthorize` | `signed_request` HMAC com `META_APP_SECRET` |
| Data Deletion | `/api/v1/webhooks/meta/data-deletion` | `signed_request` HMAC com `META_APP_SECRET` |
| Data Deletion status (pública) | `/data-deletion/{code}` (frontend) | Sem auth; código aleatório é a "auth" |

- Webhooks **sempre** retornam `200` em <10s (Meta retry indefinido). Processamento pesado vai pra NATS JetStream.
- `signed_request` é form field, NÃO JSON body. Formato: `<base64url(sig)>.<base64url(json)>`.

## Embedded Signup — mapping para Deauth

- **OBRIGATÓRIO** gravar `facebook_user_id` em `portal_connections.metadata_extra` durante o `connect_embedded_signup`. Sem isso, os webhooks Deauth/Data Deletion validam HMAC mas não encontram a conexão pra revogar (`connections_revoked=0`).
- Recupera com `wa_client.get_facebook_user_id(access_token)` → `GET /me?fields=id`.

## Embedded Signup — configuration (uma vez por App)

Em **Facebook Login for Business → Configurations → Create**:

| Campo | Valor |
|---|---|
| Login variation | **General** |
| Access token type | **System-user access token** |
| Token expiration | **Never** |
| Assets | só `Pages`, **não required** |
| Permissions | `business_management` + `whatsapp_business_management` + `whatsapp_business_messaging` |

Sai um **Configuration ID** numérico → vai pra `vite.meta_es_config_id` nos 3 yamls.

## Don'ts

- **NUNCA** `WHATSAPP_APP_SECRET` como var separada — é o mesmo `META_APP_SECRET`. Settings consolida.
- **NUNCA** APP_ID, ES_CONFIG_ID ou Graph version em `.env` — são públicos, vão pra yaml.
- **NUNCA** logar `signed_request`, `X-Hub-Signature-256`, ou body bruto de webhook em produção.
- **NUNCA** validar webhook usando `==` direto na assinatura — sempre `hmac.compare_digest` (timing-safe).
- **NUNCA** compartilhar 1 Meta App entre 2+ SaaS distintos.
- **NUNCA** marcar Pages/Ad accounts/Catalogs/Pixels/Instagram como `required` na Configuration — trava clientes que não têm aquele asset.
