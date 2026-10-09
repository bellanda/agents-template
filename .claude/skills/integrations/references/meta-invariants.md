> Reference do gate `integrations` (invariantes Meta — antes era a rule always-on `meta-integration.md`).
> Leitura curta, primeiro passo de qualquer trabalho Meta. Implementação completa → `meta-app-setup.md`.

# Meta Integration — Invariantes

Invariantes para qualquer projeto que integre com Meta (Facebook Login, WhatsApp Cloud, Instagram Graph). Implementação completa, Embedded Signup, Configuration setup, snippets HMAC → `meta-app-setup.md`.

## App Meta — 1 por SaaS

- **Cada SaaS = 1 Meta App próprio.** NUNCA compartilhe entre produtos. Hierarquia: 1 BM → N Meta Apps.
- **O mesmo App roda local/staging/prod.** Só URLs/domínios mudam por env.

## `.env` — 2 secrets, NUNCA duplicadas

```bash
META_APP_SECRET=                  # valida HMAC de X-Hub-Signature-256, signed_request, exchange ES
WHATSAPP_WEBHOOK_VERIFY_TOKEN=    # string aleatória que você escolhe; cola também na Meta
```

NUNCA crie `WHATSAPP_APP_SECRET` separado — é o mesmo `META_APP_SECRET` validando 3 surfaces distintas.

## `config/app/{env}.yaml` — público, versionado

```yaml
whatsapp:
  public_base_url: https://<projeto>.com.br # URL HTTPS que a Meta usa para webhooks
vite:
  meta_app_id: "<App ID>" # numérico do dashboard
  meta_es_config_id: "<Config ID>" # do Facebook Login for Business → Configuration
  meta_graph_api_version: v25.0
```

App ID, ES Config ID, Graph version são **PÚBLICOS** (aparecem no JS bundle). NUNCA em `.env`.

## Endpoints de webhook — naming canônico

| Webhook                        | Path                                  | Validação                                        |
| ------------------------------ | ------------------------------------- | ------------------------------------------------ |
| WhatsApp messages              | `/api/v1/webhooks/whatsapp`           | `X-Hub-Signature-256` HMAC com `META_APP_SECRET` |
| Deauthorize                    | `/api/v1/webhooks/meta/deauthorize`   | `signed_request` HMAC com `META_APP_SECRET`      |
| Data Deletion                  | `/api/v1/webhooks/meta/data-deletion` | `signed_request` HMAC com `META_APP_SECRET`      |
| Data Deletion status (pública) | `/data-deletion/{code}` (frontend)    | Sem auth; código aleatório é a "auth"            |

- Webhooks SEMPRE retornam `200` em <10s (Meta retry indefinido). Processamento pesado → NATS JetStream.
- `signed_request` é **form field**, NÃO JSON body. Formato: `<base64url(sig)>.<base64url(json)>`.
- **OBRIGATÓRIO** gravar `facebook_user_id` em `portal_connections.metadata_extra` durante `connect_embedded_signup` — sem isso Deauth/Data Deletion validam HMAC mas não acham a conexão.

## Credencial do tenant — cifrada at rest

O token de acesso que volta do Embedded Signup é **permanente** e dá acesso à WABA do cliente. Ele
NUNCA fica legível no banco:

- Cifre na camada de **repositório**, antes de todo write — não no route, senão um caminho novo
  esquece.
- Coluna dedicada com nome que denuncia o conteúdo (`api_token_encrypted`), com prefixo de versão no
  valor (`v1:`) para permitir rotação de chave.
- Guardar dentro de um JSONB genérico (`token_data`) é o anti-padrão: some no meio de outros campos e
  vaza inteiro em qualquer dump, backup ou WAL.
- Em fila/mensageria **NUNCA** trafegue o token no payload — mande `phone_number_id` e re-resolva a
  credencial no consumer.

## `postMessage` do Embedded Signup — hostname ancorado no ponto

O widget devolve `phone_number_id`/`waba_id` por `postMessage`. A checagem de origem é pelo
**hostname parseado**, ancorado em `.facebook.com`:

```ts
const FB_ROOT_HOSTNAME = "facebook.com";
function isFacebookOrigin(origin: string): boolean {
  try {
    const { protocol, hostname } = new URL(origin);
    if (protocol !== "https:") return false;
    return hostname === FB_ROOT_HOSTNAME || hostname.endsWith(`.${FB_ROOT_HOSTNAME}`);
  } catch {
    return false;
  }
}
if (!isFacebookOrigin(event.origin)) return;
```

- `event.origin.endsWith("facebook.com")` cru casa `https://evil-facebook.com` e deixa uma página
  hostil completar o handshake (auditoria 2026-06).
- Lista fixa de subdomínios (`www`/`web`/`business`) é o erro oposto: o subdomínio varia por
  conta/locale e o FINISH era descartado em silêncio (Kailos prod, 2026-10-09).
- `event.data` vem como **string JSON** (exemplo oficial faz `JSON.parse`); aceitar só objeto
  descarta tudo.
- A ordem entre o postMessage e o callback do `FB.login` **não é garantida** (doc da Meta): o
  callback espera o desfecho por alguns segundos antes de decidir. Callback do `FB.login` NUNCA
  `async` — o SDK lança "Expression is of type asyncfunction"; chame um helper async por dentro.
- Erro do widget chega como `event: "ERROR"` ou `CANCEL` com `data.error_message`/`error_code` —
  mostre o texto da Meta, não "você fechou".

## Don'ts

- **NUNCA** `WHATSAPP_APP_SECRET` separado — é `META_APP_SECRET`.
- **NUNCA** APP_ID/ES_CONFIG_ID/Graph version em `.env` — são públicos, vão em yaml.
- **NUNCA** log de `signed_request`/`X-Hub-Signature-256`/body bruto de webhook em prod.
- **NUNCA** valide HMAC com `==` direto — sempre `hmac.compare_digest` (timing-safe).
- **NUNCA** compartilhe 1 Meta App entre 2+ SaaS distintos.
- **NUNCA** guarde token de portal em claro (coluna ou JSONB) — cifre no repositório, antes do write.
- **NUNCA** valide `event.origin` por sufixo cru nem por lista fixa de subdomínios — hostname parseado ancorado em `.facebook.com`.
- **NUNCA** ponha token em payload de NATS/fila — mande `phone_number_id` e re-resolva no consumer.
- **NUNCA** marque Pages/Ad accounts/Catalogs/Pixels/Instagram como `required` na Configuration — trava clientes que não têm aquele asset.
