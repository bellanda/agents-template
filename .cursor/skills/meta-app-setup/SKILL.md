---
name: meta-app-setup
description: Runbook técnico para integrar com a plataforma Meta (Facebook Login for Business, WhatsApp Business Cloud API, Instagram Graph) — Embedded Signup flow, webhooks Deauthorize/Data Deletion, HMAC validation (signed_request + X-Hub-Signature-256), separação .env (secrets) vs yaml (público), 1 Meta App por SaaS, naming canônico dos endpoints. INVOCAR ANTES de criar/alterar qualquer integração Meta — novo endpoint /webhooks/meta/*, FB.login no frontend, exchange de code do Embedded Signup, validação HMAC de webhook, gravação de facebook_user_id em portal_connections, popular META_APP_SECRET/WHATSAPP_WEBHOOK_VERIFY_TOKEN, ou popular meta_app_id/meta_es_config_id em yaml. Complementa rule `meta-integration.md` (invariantes) e reference `references/meta/meta-app-setup.md` (passo-a-passo dashboard).
---

# meta-app-setup

Runbook para implementar integrações com a Meta. Os invariantes vivem em `meta-integration.md` (rule). Aqui está o código de referência + checklist de troubleshooting.

## 0. Antes de codar

Confirma que existe:

1. **Meta App próprio do SaaS** (1 por produto). Se não existe, ver `references/meta/meta-app-setup.md` passos 1–3.
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
            "quality_rating": phone_info.get("quality_rating"),
        },
    )
    return {"status": "active", "portal": portal,
            "external_username": connection["external_username"]}
```

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
const SESSION_INFO_VERSION = 3;

export function FacebookBusinessLoginButton({
  appId, configId, graphApiVersion = "v25.0", onSuccess, onError,
}: Props) {
  const [sdkReady, setSdkReady] = useState(typeof window !== "undefined" && !!window.FB);
  const sessionInfoRef = useRef<{ phoneNumberId?: string; wabaId?: string }>({});

  // postMessage do widget envia phone_number_id + waba_id ANTES do FB.login callback.
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (!event.origin.endsWith("facebook.com")) return;
      const data = event.data;
      if (data?.type !== "WA_EMBEDDED_SIGNUP") return;
      if (data.event === "FINISH" && data.data) {
        sessionInfoRef.current = {
          phoneNumberId: data.data.phone_number_id,
          wabaId: data.data.waba_id,
        };
      }
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
    sessionInfoRef.current = {};
    window.FB!.login(
      (response) => {
        const code = response?.authResponse?.code;
        const { phoneNumberId, wabaId } = sessionInfoRef.current;
        if (!code || !phoneNumberId || !wabaId) {
          onError("ES cancelado ou sem session_info");
          return;
        }
        onSuccess({ code, phoneNumberId, wabaId });
      },
      {
        config_id: configId,
        response_type: "code",
        override_default_response_type: true,
        extras: { feature: "whatsapp_embedded_signup", sessionInfoVersion: SESSION_INFO_VERSION, setup: {} },
      }
    );
  };

  return <Button onClick={handleClick} disabled={!sdkReady}>Conectar com Facebook</Button>;
}
```

Vite expõe `VITE_META_APP_ID`, `VITE_META_ES_CONFIG_ID`, `VITE_META_GRAPH_API_VERSION` automaticamente a partir do bloco `vite:` do yaml.

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
| ES finaliza sem phone_number_id/waba_id no `sessionInfoRef` | postMessage não chegou (listener filtra outras origens) | Confirma `origin.endsWith("facebook.com")` no listener |
| `Invalid OAuth access token` no exchange_es_code | `code` expirou (~10s) | Cliente lento; refazer flow |
| Webhook `SIGNATURE MISMATCH` | `META_APP_SECRET` errado | Re-copia da Meta, restart |
| `meta_deauthorize ... revoked=0` mas validou HMAC | Conexão criada via token manual (sem `facebook_user_id`) | Esperado — só ES grava esse campo |
| Status page sempre "processing" | `deletion_completed_at` nunca é populado | Não implementamos purge físico ainda — só marca |
| `register_phone_number failed: 133005` | Número já registrado | Já tratamos — `{"already_registered": true}` |
| Verify token GET retorna 403 | Token em `.env` ≠ token no dashboard | Re-copia caractere por caractere |
