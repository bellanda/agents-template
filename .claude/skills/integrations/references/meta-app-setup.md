> Reference do gate `integrations` (runbook técnico completo de integração Meta: WhatsApp Cloud,
> Embedded Signup, webhooks Deauth/Data-Deletion, HMAC). Invariantes → `meta-invariants.md`.

# Meta — Runbook de implementação

Runbook para implementar integrações com a Meta. Os invariantes vivem em `meta-invariants.md` (reference irmã). Aqui está o código de referência + checklist de troubleshooting.

## 0. Antes de codar

Confirma que existe:

1. **Meta App próprio do SaaS** (1 por produto). Se não existe, criar em developers.facebook.com (App + Business Manager) e a Configuration do Facebook Login for Business (gera o `ES_CONFIG_ID`) — ver `meta-invariants.md`.
2. **Configuration do Facebook Login for Business** criada (gera `ES_CONFIG_ID`).
3. **Domínios + OAuth Redirects** registrados nos 3 envs no dashboard.

Sem isso, o código abaixo compila mas falha em runtime com erros opacos da Meta.

---

## 1. Settings — pydantic

```python
# config/settings.py
class WhatsappSettings(BaseModel):
    public_base_url: str  # https://dev-tunnel.bellanda.app etc
    # ... outros campos

class ViteSettings(BaseModel):
    # ... backend_url, frontend_url, google_*
    meta_app_id: str = ""             # público — yaml
    meta_es_config_id: str = ""       # público — yaml
    meta_graph_api_version: str = "v25.0"

class Settings(BaseModel):
    # ... outros campos
    # ÚNICOS secrets Meta — .env
    meta_app_secret: SecretStr | None = Field(default_factory=lambda: _opt("META_APP_SECRET"))
    whatsapp_webhook_verify_token: SecretStr | None = Field(
        default_factory=lambda: _opt("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
    )
```

```python
# config/integrations.py
class IntegrationsConfig:
    META_APP_ID: str = settings.vite.meta_app_id
    META_APP_SECRET: str | None = _opt_secret(settings.meta_app_secret)
    META_ES_CONFIG_ID: str = settings.vite.meta_es_config_id
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str | None = _opt_secret(settings.whatsapp_webhook_verify_token)
    WHATSAPP_PUBLIC_BASE_URL: str = settings.whatsapp.public_base_url
```

---

## 2. WhatsApp client — helpers ES

```python
# api/services/portals/whatsapp/client.py
import secrets
from curl_cffi import AsyncSession

META_GRAPH_API_VERSION = "v25.0"
META_GRAPH_BASE = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}"
HTTP_MINIMUM_STATUS_CODE_FOR_CLIENT_ERROR = 400
REGISTER_PIN_DIGITS = 6


class WhatsAppClient:
    def _headers(self, api_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}

    async def exchange_es_code(self, code: str, app_id: str, app_secret: str) -> str:
        """FB.login code → permanent business access token."""
        async with AsyncSession(impersonate="chrome") as session:
            response = await session.get(
                f"{META_GRAPH_BASE}/oauth/access_token",
                params={"client_id": app_id, "client_secret": app_secret, "code": code},
            )
            body = response.json()
            if response.status_code >= HTTP_MINIMUM_STATUS_CODE_FOR_CLIENT_ERROR:
                detail = body.get("error", {}).get("message", str(response.status_code))
                raise RuntimeError(f"Embedded Signup code exchange failed: {detail}")
            token = body.get("access_token")
            if not token:
                raise RuntimeError("Embedded Signup response missing access_token")
            return str(token)

    async def get_facebook_user_id(self, api_token: str) -> str:
        """App-scoped Facebook user ID. Chave para mapear Deauth → portal_connection."""
        async with AsyncSession(impersonate="chrome") as session:
            response = await session.get(
                f"{META_GRAPH_BASE}/me",
                params={"fields": "id"},
                headers=self._headers(api_token),
            )
            body = response.json()
            if response.status_code >= HTTP_MINIMUM_STATUS_CODE_FOR_CLIENT_ERROR:
                detail = body.get("error", {}).get("message", str(response.status_code))
                raise RuntimeError(f"get_facebook_user_id failed: {detail}")
            return str(body["id"])

    async def subscribe_app_to_waba(self, waba_id: str, api_token: str) -> dict:
        """Idempotente. Necessário pra começar a receber webhooks."""
        async with AsyncSession(impersonate="chrome") as session:
            response = await session.post(
                f"{META_GRAPH_BASE}/{waba_id}/subscribed_apps",
                headers=self._headers(api_token),
            )
            body = response.json()
            if response.status_code >= HTTP_MINIMUM_STATUS_CODE_FOR_CLIENT_ERROR:
                detail = body.get("error", {}).get("message", str(response.status_code))
                raise RuntimeError(f"subscribe_app_to_waba failed: {detail}")
            return body

    async def register_phone_number(
        self, phone_number_id: str, api_token: str, pin: str | None = None
    ) -> dict:
        """Precondição pra enviar/receber. Idempotente em prática (já-registrado vira 200)."""
        pin_value = pin or "".join(secrets.choice("0123456789") for _ in range(REGISTER_PIN_DIGITS))
        async with AsyncSession(impersonate="chrome") as session:
            response = await session.post(
                f"{META_GRAPH_BASE}/{phone_number_id}/register",
                json={"messaging_product": "whatsapp", "pin": pin_value},
                headers=self._headers(api_token),
            )
            body = response.json()
            if response.status_code >= HTTP_MINIMUM_STATUS_CODE_FOR_CLIENT_ERROR:
                err_code = body.get("error", {}).get("code")
                if err_code in {133005, 133006}:  # já registrado
                    return {"already_registered": True}
                detail = body.get("error", {}).get("message", str(response.status_code))
                raise RuntimeError(f"register_phone_number failed: {detail}")
            return body
```

---

## 3. Endpoint `/embedded-signup` — orquestra exchange + subscribe + register

```python
# api/routes/portals/portals.py
@router.post("/{portal}/embedded-signup")
@permission_service.require_authentication()
@permission_service.require_permission_in_org("portal:manage", "org_id")
async def connect_embedded_signup(
    request: Request, org_id: UUID, portal: str, conn: Connection = Depends(get_conn)
) -> dict:
    if portal != "whatsapp":
        raise BadRequestError(detail=f"Portal '{portal}' não suporta Embedded Signup")

    app_id = settings.vite.meta_app_id
    app_secret_secret = settings.meta_app_secret
    if not app_id or not app_secret_secret:
        raise BadRequestError(detail="Embedded Signup não configurado")

    body = await request.json()
    code = (body.get("code") or "").strip()
    phone_number_id = (body.get("phone_number_id") or "").strip()
    waba_id = (body.get("waba_id") or "").strip()
    # v4: o FINISH passou a trazer o Business Manager do cliente. Opcional — nem toda
    # variação do fluxo manda, e o handshake não depende dele.
    business_id = (body.get("business_id") or "").strip() or None
    if not code or not phone_number_id or not waba_id:
        raise BadRequestError(detail="code, phone_number_id e waba_id obrigatórios")

    app_secret = app_secret_secret.get_secret_value()
    try:
        access_token = await wa_client.exchange_es_code(code, app_id, app_secret)
        await wa_client.subscribe_app_to_waba(waba_id, access_token)
        await wa_client.register_phone_number(phone_number_id, access_token)
        phone_info = await wa_client.verify_credentials(phone_number_id, access_token)
        # CRÍTICO — sem isso webhooks Deauth/Data Deletion não acham a conexão
        facebook_user_id = await wa_client.get_facebook_user_id(access_token)
    except RuntimeError as exc:
        raise BadRequestError(detail=f"Embedded Signup falhou: {exc}") from exc

    connection = await portal_connection_repository.upsert(
        conn, org_id, portal,
        status="active",
        external_user_id=phone_number_id,
        external_username=phone_info.get("verified_name", phone_number_id),
        token_data={
            "phone_number_id": phone_number_id,
            "api_token": access_token,
            "waba_id": waba_id,
            "source": "embedded_signup",
        },
        metadata_extra={
            "waba_id": waba_id,
            "facebook_user_id": facebook_user_id,  # ← chave do mapping
            "business_id": business_id,  # v4; fica no JSONB, nenhuma query lê hoje
            "source": "embedded_signup",
            "quality_rating": phone_info.get("quality_rating"),
        },
    )
    return {"status": "active", "portal": portal,
            "external_username": connection["external_username"]}
```

### 3b. Caminho de token manual — faz o MESMO handshake ou não faz nada

Quase todo projeto ganha, para QA, um formulário que aceita `phone_number_id` + token
colados à mão. **Ele não pode parar em `verify_credentials`.** Verificar credencial só
prova que o token é válido; quem faz a Meta *entregar mensagem* é o
`subscribe_app_to_waba`. Sem ele a conexão nasce com badge verde na tela e inbound morto —
e o sintoma ("conectei e não chega nada") não aponta para o formulário.

Então o caminho manual exige **três** campos (`phone_number_id`, `waba_id`, `api_token`) e
roda a mesma sequência do ES, trocando o `exchange_es_code` pelo token informado:
`subscribe_app_to_waba` → `register_phone_number` → `verify_credentials` → `upsert(...,
waba_id=waba_id, metadata_extra={"source": "manual_token"})`.

O que **continua** faltando, e precisa de comentário no código: um System User token não
tem usuário do Facebook por trás, então não existe `facebook_user_id` — os webhooks
Deauthorize e Data Deletion não conseguem mapear essa conexão (`revoke_by_metadata_field`
não acha linha) e a revogação vira trabalho manual. Por isso o bloco fica **atrás de
`isSuperuser`**, não exposto ao cliente final.

---

## 4. `signed_request` decoder (Deauth + Data Deletion)

```python
# api/services/meta/signed_request.py
import base64
import binascii
import hashlib
import hmac
import json

from api.core.exceptions import BadRequestError


def decode_signed_request(signed_request: str, app_secret: str) -> dict:
    """Validate Meta's signed_request and return its JSON payload.

    Format: <base64url(sig)>.<base64url(payload_json)>
    Sig is HMAC-SHA256(payload_b64, app_secret).
    """
    try:
        sig_b64, payload_b64 = signed_request.split(".", 1)
    except ValueError:
        raise BadRequestError(detail="malformed signed_request")

    # base64url: garantir padding correto
    def _pad(s: str) -> str:
        return s + "=" * (-len(s) % 4)

    try:
        sig = base64.urlsafe_b64decode(_pad(sig_b64))
        payload_bytes = base64.urlsafe_b64decode(_pad(payload_b64))
    except (binascii.Error, ValueError) as exc:
        raise BadRequestError(detail="invalid base64 in signed_request") from exc

    expected_sig = hmac.new(
        app_secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(sig, expected_sig):
        raise BadRequestError(detail="signed_request signature mismatch")

    try:
        return json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise BadRequestError(detail="signed_request payload not JSON") from exc
```

---

## 5. Endpoints `/webhooks/meta/{deauthorize,data-deletion}`

```python
# api/routes/portals/webhooks.py
import secrets

@router.post("/meta/deauthorize")
async def meta_deauthorize(
    signed_request: str = Form(...), conn: Connection = Depends(get_conn)
) -> dict:
    secret = integrations_config.META_APP_SECRET
    if not secret:
        raise BadRequestError(detail="META_APP_SECRET not configured")
    payload = decode_signed_request(signed_request, secret)
    user_id = str(payload.get("user_id") or "").strip()
    if not user_id:
        return {"status": "ok"}  # nada a fazer
    affected = await portal_connection_repository.revoke_by_metadata_field(
        conn, "facebook_user_id", user_id
    )
    logger.info("meta_deauthorize fb_user_id=%s revoked=%d", user_id, len(affected))
    return {"status": "ok", "revoked": len(affected)}


@router.post("/meta/data-deletion")
async def meta_data_deletion(
    signed_request: str = Form(...), conn: Connection = Depends(get_conn)
) -> dict:
    secret = integrations_config.META_APP_SECRET
    if not secret:
        raise BadRequestError(detail="META_APP_SECRET not configured")
    payload = decode_signed_request(signed_request, secret)
    user_id = str(payload.get("user_id") or "").strip()
    if not user_id:
        return {"status": "ok"}

    confirmation_code = secrets.token_hex(16)
    affected = await portal_connection_repository.mark_deletion_requested(
        conn, user_id, confirmation_code
    )
    logger.info(
        "meta_data_deletion fb_user_id=%s code=%s flagged=%d",
        user_id, confirmation_code, len(affected),
    )
    return {
        "url": f"{integrations_config.FRONTEND_URL}/data-deletion/{confirmation_code}",
        "confirmation_code": confirmation_code,
    }
```

Webhook handler precisa de 3 métodos no `portal_connection_repository`:

```python
async def revoke_by_metadata_field(
    conn, field_name: str, field_value: str
) -> list[dict]:
    rows = await conn.fetch(
        """
        UPDATE portal_connections
           SET status = 'revoked', updated_at = NOW()
         WHERE metadata_extra ->> $1 = $2
           AND status != 'revoked'
         RETURNING id, organization_id, portal
        """,
        field_name, field_value,
    )
    return [dict(r) for r in rows]


async def mark_deletion_requested(
    conn, facebook_user_id: str, confirmation_code: str
) -> list[dict]:
    rows = await conn.fetch(
        """
        UPDATE portal_connections
           SET status = 'revoked',
               metadata_extra = jsonb_set(
                   jsonb_set(
                       COALESCE(metadata_extra, '{}'::jsonb),
                       '{deletion_confirmation_code}', to_jsonb($2::text)
                   ),
                   '{deletion_requested_at}', to_jsonb(NOW()::text)
               ),
               updated_at = NOW()
         WHERE metadata_extra ->> 'facebook_user_id' = $1
         RETURNING id, organization_id, portal
        """,
        facebook_user_id, confirmation_code,
    )
    return [dict(r) for r in rows]


async def find_by_deletion_code(conn, code: str) -> dict | None:
    row = await conn.fetchrow(
        "SELECT id, organization_id, portal, metadata_extra "
        "  FROM portal_connections "
        " WHERE metadata_extra ->> 'deletion_confirmation_code' = $1",
        code,
    )
    return dict(row) if row else None
```

---

## 6. Webhook WhatsApp messages — `X-Hub-Signature-256`

```python
import hmac
import hashlib

def _verify_whatsapp_signature(raw_body: bytes, signature_header: str, app_secret: str) -> bool:
    """Validate X-Hub-Signature-256 header from Meta WhatsApp webhook."""
    if not signature_header.startswith("sha256="):
        return False
    received_sig = signature_header[len("sha256="):]
    expected_sig = hmac.new(
        app_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(received_sig, expected_sig)


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request) -> dict:
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    app_secret = integrations_config.META_APP_SECRET or ""

    if app_secret and signature and not _verify_whatsapp_signature(raw_body, signature, app_secret):
        logger.warning("WA webhook SIGNATURE MISMATCH — check META_APP_SECRET")
        return {"status": "error", "reason": "invalid_signature"}

    # 200 sempre em <10s. Empilha no NATS pra consumer fazer trabalho pesado.
    body = await request.json()
    # ... publish para JetStream
    return {"status": "ok"}
```

Verify token (GET handshake quando Meta valida a URL):

```python
@router.get("/whatsapp")
async def whatsapp_webhook_verify(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
) -> PlainTextResponse:
    expected = integrations_config.WHATSAPP_WEBHOOK_VERIFY_TOKEN or ""
    if hub_mode == "subscribe" and hmac.compare_digest(hub_verify_token, expected):
        return PlainTextResponse(content=hub_challenge, status_code=200)
    return PlainTextResponse(content="Verification failed", status_code=403)
```

---

## 7. Frontend — Botão "Conectar com Facebook" (Embedded Signup)

```tsx
// components/whatsapp-setup/FacebookBusinessLoginButton.tsx
const FB_SDK_URL = "https://connect.facebook.net/en_US/sdk.js";
const FB_SDK_SCRIPT_ID = "facebook-jssdk";

// Origens EXATAS de onde o widget posta. Allowlist por igualdade — um sufixo
// (`endsWith("facebook.com")`) tambem casa `https://evil-facebook.com`.
const FB_EMBEDDED_SIGNUP_ORIGINS = new Set([
  "https://www.facebook.com",
  "https://web.facebook.com",
  "https://business.facebook.com",
]);

// O `event` do postMessage é o DISCRIMINADOR do desfecho. Sem ele, "fechou a janela no
// meio", "terminou sem escolher número" (a Meta permite desde a v3) e "o widget nunca
// respondeu" chegam ao callback como o MESMO objeto vazio — e o usuário recebe a mesma
// mensagem errada nos três casos.
type SignupOutcome =
  | { kind: "none" }
  | { kind: "finished"; phoneNumberId?: string; wabaId?: string; businessId?: string }
  | { kind: "cancelled"; currentStep?: string }
  | { kind: "unsupported"; event: string };

const readId = (v: unknown) => (typeof v === "string" && v.length > 0 ? v : undefined);

export function FacebookBusinessLoginButton({
  appId, configId, graphApiVersion = "v25.0", onSuccess, onError,
}: Props) {
  const [sdkReady, setSdkReady] = useState(typeof window !== "undefined" && !!window.FB);
  const outcomeRef = useRef<SignupOutcome>({ kind: "none" });

  // Formas que a Meta envia:
  //   FINISH → data: { phone_number_id, waba_id, business_id, … }
  //   CANCEL → data: { current_step }
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (!FB_EMBEDDED_SIGNUP_ORIGINS.has(event.origin)) return;
      // A Meta posta `event.data` como STRING JSON (o exemplo oficial faz JSON.parse).
      // Aceitar só objeto descartou todo FINISH em prod (Kailos, 2026-10-09): o `code`
      // chegava, o desfecho ficava `none` e o usuário via "widget não respondeu".
      let message: Record<string, unknown> | undefined;
      try {
        const raw: unknown = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
        if (raw && typeof raw === "object") message = raw as Record<string, unknown>;
      } catch {
        return; // outros frames do facebook.com postam string não-JSON no mesmo canal
      }
      if (!message) return;
      if (message.type !== "WA_EMBEDDED_SIGNUP") return;
      const data = (message.data ?? {}) as Record<string, unknown>;
      if (message.event === "FINISH") {
        outcomeRef.current = {
          kind: "finished",
          phoneNumberId: readId(data.phone_number_id),
          wabaId: readId(data.waba_id),
          businessId: readId(data.business_id),
        };
        return;
      }
      if (message.event === "CANCEL") {
        outcomeRef.current = { kind: "cancelled", currentStep: readId(data.current_step) };
        return;
      }
      // Variações do fluxo que este app não implementa — hoje coexistência
      // (`FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING`) e WABA sem número
      // (`FINISH_ONLY_WABA`). Só chegam se alguém marcar o produto na Configuration,
      // e em v4 isso é decisão de painel, não de código. Nomear o evento é o que
      // transforma "não funciona" numa frase que diz onde mexer.
      outcomeRef.current = { kind: "unsupported", event: String(message.event ?? "") };
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  // Init SDK uma vez por mount, idempotente.
  useEffect(() => {
    if (!appId) return;
    if (window.FB) {
      window.FB.init({ appId, cookie: true, xfbml: true, version: graphApiVersion });
      setSdkReady(true);
      return;
    }
    window.fbAsyncInit = () => {
      window.FB?.init({ appId, cookie: true, xfbml: true, version: graphApiVersion });
      setSdkReady(true);
    };
    if (document.getElementById(FB_SDK_SCRIPT_ID)) return;
    const script = document.createElement("script");
    script.id = FB_SDK_SCRIPT_ID;
    script.async = true;
    script.defer = true;
    script.crossOrigin = "anonymous";
    script.src = FB_SDK_URL;
    document.body.appendChild(script);
  }, [appId, graphApiVersion]);

  const handleClick = () => {
    outcomeRef.current = { kind: "none" };
    window.FB!.login(
      (response) => {
        const outcome = outcomeRef.current;
        // `cancelled` vem ANTES do teste de `code`: quem fecha o widget também volta
        // sem code, e checar o code primeiro jogaria todo mundo na mensagem genérica
        // — junto com o `current_step`, o único dado que diz onde ele parou.
        if (outcome.kind === "cancelled") {
          const step = outcome.currentStep ? ` (etapa: ${outcome.currentStep})` : "";
          onError(`Você fechou o Embedded Signup antes de concluir${step}.`);
          return;
        }
        if (outcome.kind === "unsupported") {
          onError(
            `A Meta devolveu um evento que este app não trata (${outcome.event}). ` +
              "Confira os produtos marcados na Configuration do Embedded Signup."
          );
          return;
        }
        const code = response?.authResponse?.code;
        if (!code) return onError("Login cancelado ou code não retornado pela Meta.");
        if (outcome.kind === "none")
          return onError("O widget da Meta não respondeu. Verifique o bloqueador de pop-ups.");
        if (!outcome.phoneNumberId)
          return onError("O fluxo terminou sem número. Refaça e escolha um no widget.");
        if (!outcome.wabaId)
          return onError("O fluxo terminou sem WABA. Refaça e selecione a conta no widget.");
        onSuccess({
          code,
          phoneNumberId: outcome.phoneNumberId,
          wabaId: outcome.wabaId,
          businessId: outcome.businessId,
        });
      },
      {
        config_id: configId,
        response_type: "code",
        override_default_response_type: true,
        // v4: `extras` só carrega `setup` (prefill opcional). Ver seção abaixo.
        extras: { setup: {} },
      }
    );
  };

  return <Button onClick={handleClick} disabled={!sdkReady}>Conectar com Facebook</Button>;
}
```

Vite expõe `VITE_META_APP_ID`, `VITE_META_ES_CONFIG_ID`, `VITE_META_GRAPH_API_VERSION` automaticamente a partir do bloco `vite:` do yaml.

### Versão do Embedded Signup — v4 é a única viva

O ES tem versão PRÓPRIA, independente da versão da Graph API (`v25.0` na URL não diz
nada sobre isto). Meta descontinua **v2 e v3 em 15/10/2026**; v4 saiu em 08/10/2025.

**Quem escolhe a versão é o `extras`**, e é por eliminação — não existe `version: "v4"`:

| Versão | Selector no código                                      |
| ------ | ------------------------------------------------------- |
| v2     | `extras: { sessionInfoVersion: "3", featureType: ... }` |
| v3     | `extras: { version: "v3", featureType: ... }`           |
| **v4** | `extras: { setup: {} }` — **e nada mais**               |

Ou seja: **`sessionInfoVersion` ou `version` presentes = você está numa versão morta.**
`feature: "whatsapp_embedded_signup"` nunca foi parâmetro documentado — some junto.

Em v4 o que era `featureType`/`features` no código passa a ser **produto marcado na
Facebook Login for Business → Configurations**. O `config_id` deixou de ser só um
ponteiro de escopos e virou o lugar onde a variação do fluxo é decidida: coexistência
(WhatsApp Business app onboarding), Marketing Messages, Click to WhatsApp Ads.

**Na virada, a maioria das integrações é convertida automaticamente para v4** — mas
`only_waba_sharing`, `marketing_messages_lite` e **`coex`** (coexistência) **não são**, e
param de funcionar. Se o `featureType` do projeto for um desses três, a migração é
obrigatória e tem prazo; se o `extras` só tinha `sessionInfoVersion`/`feature`, a conversão
é automática e a limpeza do código é higiene, não emergência.

O `postMessage WA_EMBEDDED_SIGNUP` continua entregando `data.phone_number_id` e
`data.waba_id` em v4, e ganhou `business_id` (guarde no `metadata_extra`, não em coluna —
hoje nenhuma query lê) mais listas opcionais de assets. O que muda é o **handler**: além
de `FINISH` e `CANCEL` (`data.current_step` — a etapa onde o lojista desistiu, o dado que
o suporte precisa), existem `FINISH_ONLY_WABA` e
`FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING`. Tratar só `FINISH` faz os outros desfechos
caírem no mesmo estado vazio de "o widget nunca respondeu" — três causas, uma mensagem, e
ela errada em dois dos casos. O `code` continua com TTL de ~30s: mande pro backend na hora.

### CSP — sem isto o botão NUNCA sai do spinner

O SDK vem de `connect.facebook.net` e a app quase sempre serve um
`Content-Security-Policy` restritivo. Três diretivas precisam ceder, e **o mesmo host
entra em duas delas**:

| Diretiva      | Hosts                                                                                                       | Por quê                                                                                     |
| ------------- | ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `script-src`  | `https://connect.facebook.net`                                                                              | serve o `sdk.js`                                                                            |
| `connect-src` | `https://connect.facebook.net` · `https://graph.facebook.com` · `https://www.facebook.com`                  | a PRIMEIRA coisa que o SDK faz é `fetch` de `connect.facebook.net/app_config/json/<app_id>` |
| `frame-src`   | `https://www.facebook.com` · `https://web.facebook.com` · `https://business.facebook.com` · `https://staticxx.facebook.com` | o SDK cria o iframe `xd_arbiter`, que carrega o `postMessage` do widget                     |

**A armadilha é liberar só o `script-src`**: o script carrega, o `FB.init` roda, e o SDK
morre no fetch seguinte. Nada aparece na tela — o botão fica desabilitado para sempre e o
erro vive só no console. Regra geral: **host de terceiro que serve script quase sempre
também precisa de `connect-src`**, e se ele renderiza iframe, de `frame-src`.

`Cross-Origin-Opener-Policy` tem que ser `same-origin-allow-popups` (NUNCA `same-origin`),
senão o popup do `FB.login` não devolve o `postMessage` para a página que o abriu.

---

## 8. Data Deletion status page (pública)

```tsx
// routes/data-deletion/$code.tsx
export const Route = createFileRoute("/data-deletion/$code")({
  component: DataDeletionStatusPage,
});

function DataDeletionStatusPage() {
  const { code } = Route.useParams();
  const { data } = useQuery({
    queryKey: ["data-deletion", code],
    queryFn: () => api.get<DeletionStatus>(`/api/meta/deletion-status/${code}`),
    refetchInterval: 15_000,  // auto-poll
  });
  // ... render status: pending/processing/completed
}
```

Status endpoint backend (público, sem auth — código aleatório É a "auth"):

```python
@public_meta_router.get("/meta/deletion-status/{code}")
async def meta_deletion_status(code: str, conn: Connection = Depends(get_conn)) -> dict:
    # Valida formato (hex 32 chars) antes de tocar DB pra evitar enumeration.
    if len(code) != 32 or not all(c in "0123456789abcdef" for c in code):
        raise BadRequestError(detail="invalid code format")
    row = await portal_connection_repository.find_by_deletion_code(conn, code)
    if not row:
        return {"status": "not_found", "code": code}
    meta = row["metadata_extra"] or {}
    return {
        "status": "completed" if meta.get("deletion_completed_at") else "processing",
        "code": code,
        "requested_at": meta.get("deletion_requested_at"),
        "completed_at": meta.get("deletion_completed_at"),
    }
```

---

## 9. Smoke test pós-setup

```bash
cd backend && uv run python -c "
from config.integrations import IntegrationsConfig as I
print('APP_ID:        ', I.META_APP_ID)
print('ES_CONFIG_ID:  ', I.META_ES_CONFIG_ID)
print('APP_SECRET:    ', 'set' if I.META_APP_SECRET else 'MISSING')
print('VERIFY_TOKEN:  ', 'set' if I.WHATSAPP_WEBHOOK_VERIFY_TOKEN else 'MISSING')
print('PUBLIC_BASE:   ', I.WHATSAPP_PUBLIC_BASE_URL)
"
```

Tudo populado → frontend mostra botão "Conectar com Facebook" funcional. Algum vazio → revisar yaml ou `.env`.

---

## 10. Troubleshooting

| Sintoma | Causa | Fix |
|---|---|---|
| Botão FB desabilitado | `VITE_META_APP_ID` ou `VITE_META_ES_CONFIG_ID` vazio | Confirma yaml + restart `bun dev` |
| FB.login retorna sem `code` | Cliente fechou o popup | Retry, nada a fazer |
| ES finaliza sem phone_number_id/waba_id no `sessionInfoRef` | postMessage não chegou (listener filtra outras origens) | Confirma que a origem real está na allowlist exata `FB_EMBEDDED_SIGNUP_ORIGINS` — NUNCA "conserte" trocando por `endsWith` |
| `Invalid OAuth access token` no exchange_es_code | `code` expirou (~10s) | Cliente lento; refazer flow |
| Webhook `SIGNATURE MISMATCH` | `META_APP_SECRET` errado | Re-copia da Meta, restart |
| `meta_deauthorize ... revoked=0` mas validou HMAC | Conexão criada via token manual (sem `facebook_user_id`) | Esperado — só ES grava esse campo |
| Status page sempre "processing" | `deletion_completed_at` nunca é populado | Não implementamos purge físico ainda — só marca |
| `register_phone_number failed: 133005` | Número já registrado | Já tratamos — `{"already_registered": true}` |
| Verify token GET retorna 403 | Token em `.env` ≠ token no dashboard | Re-copia caractere por caractere |
