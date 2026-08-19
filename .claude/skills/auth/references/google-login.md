> Reference do gate `auth` (Login com Google: popup auth-code → exchange → verify id_token via JWKS). Pareia com `auth-hardened.md`.

# Google Login — popup auth-code + M1 hybrid

Stack: `@react-oauth/google` (front, popup auth-code) + `curl_cffi` (exchange do code) + `google-auth` (verify id_token via JWKS) + JWT/cookie do `auth-hardened.md`. Pareado com `auth-hardened.md` (sessão/cookie/verify); setup do Cloud Console coberto inline abaixo (Authorized JavaScript origins; sem redirect URIs no popup).

## 0. Decisões fixas (não re-derivar)

- **Fluxo: popup auth-code (`redirect_uri=postmessage`)**, NÃO redirect-callback. Popup × redirect é
  só UX — o backend é idêntico (recebe `code` → troca → verifica → emite sessão). Popup é auth-code,
  code single-use, trocado server-side com o secret; nunca persiste no JS.
- **Sessão: M1 hybrid** — access JWT curto em **memória** + refresh opaco em **cookie HttpOnly**
  (= `auth-hardened`). API stateless, portável. NÃO migrar p/ BFF/session-cookie sem decisão explícita.
- **Path canônico: `POST /api/v1/auth/google`** (login é `auth`, coerente com `/auth/token`). Perfil
  é `GET /api/v1/accounts/me`. NUNCA login sob `/accounts/auth/google` (drift a corrigir).
- **Console: só Authorized JavaScript origins.** O popup NÃO usa redirect URIs — cadastrá-las é
  config morta. Ver reference passo 2.

## 1. Fluxo (popup auth-code)

```
SPA --click--> GSI popup --consent--> Google
Google --code via postMessage--> SPA            (página NÃO recarrega)
SPA  --POST /api/v1/auth/google { code }-->  Backend
Backend --code + client_secret (redirect_uri=postmessage)--> Google /token  -->  id_token
Backend verifica id_token (JWKS, auth-hardened §6) -> get-or-create user -> emite par M1
Backend --access_token (JSON, memória) + refresh (cookie HttpOnly)--> SPA
```

`postmessage` é o sentinel do Google p/ popup — validado internamente, NÃO comparado contra redirect URIs.

## 2. Config — público (yaml) vs secret (.env)

```yaml
# config/app/{local,staging,prod}.yaml
google:
  oauth_client_id: "<id>.apps.googleusercontent.com" # público — audience da verificação
vite:
  google_client_id: "<id>.apps.googleusercontent.com" # mesmo valor — vai no JS bundle
```

```bash
# .env  (ÚNICO secret do Google login)
GOOGLE_OAUTH_CLIENT_SECRET=
```

```python
# config/auth.py
class AuthConfig:
    GOOGLE_OAUTH_CLIENT_ID: str = settings.google.oauth_client_id
    GOOGLE_OAUTH_CLIENT_SECRET: str = (
        settings.google_oauth_client_secret.get_secret_value()
        if settings.google_oauth_client_secret
        else ""
    )
```

`client_id` é público (audience na verificação + vai no bundle). `client_secret` é o único segredo.
**Quando Google é o único login, NÃO crie flag `GOOGLE_LOGIN_ENABLED`** — flag p/ o único método de
login é contraditória. (Flag só faz sentido enquanto Google coexiste como opção secundária.)

## 3. Backend — schema do request

```python
# api/schemas/auth/auth.py
class GoogleLoginRequest(BaseModel):
    """O popup devolve um authorization code curto; o backend troca por id_token."""

    code: str = Field(..., description="OAuth authorization code from the Google popup")
    redirect_uri: str = Field("postmessage", description="popup-mode sentinel; matches the front")
```

## 4. Backend — `google_oauth_service`

Troca o code → verifica id_token (via `auth-hardened` §6) → get-or-create user → emite par M1
(reusa `jwt_service` do `auth-hardened`, mesma family-per-login do password path).

```python
# api/services/auth/google_oauth_service.py
import anyio
import structlog
from asyncpg import Connection
from curl_cffi import AsyncSession
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from api.core.exceptions import AuthenticationError
from api.models.auth.user import User
from api.repositories.auth.user_repository import user_repository
from api.services.auth.jwt_service import jwt_service
from config.auth import auth_config

log = structlog.get_logger(__name__)

GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
HTTP_CLIENT_ERROR = 400


class GoogleOAuthService:
    async def exchange_code_for_id_token(self, code: str, redirect_uri: str) -> str:
        """Trade the popup authorization code for an id_token JWT.

        redirect_uri='postmessage' is Google's popup sentinel — must match exactly
        what the frontend popup advertised.
        """
        async with AsyncSession() as session:
            response = await session.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": auth_config.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": auth_config.GOOGLE_OAUTH_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        if response.status_code >= HTTP_CLIENT_ERROR:
            log.warning("google_code_exchange_failed", status=response.status_code)
            raise AuthenticationError(detail="Google code exchange failed")
        id_token_str = (response.json() or {}).get("id_token")
        if not id_token_str:
            raise AuthenticationError(detail="Google response missing id_token")
        return id_token_str

    async def verify_google_token(self, token: str) -> dict:
        # google-auth é sync → roda em thread (anyio). Valida assinatura/aud/exp via JWKS.
        def verify_sync() -> dict:
            try:
                return id_token.verify_oauth2_token(
                    token, google_requests.Request(), audience=auth_config.GOOGLE_OAUTH_CLIENT_ID
                )
            except ValueError as exc:
                raise AuthenticationError(detail="Invalid Google token") from exc

        claims = await anyio.to_thread.run_sync(verify_sync)
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise AuthenticationError(detail="Invalid Google token issuer")
        if not claims.get("email_verified", False):
            raise AuthenticationError(detail="Email not verified by Google")
        return claims

    async def authenticate_with_google(self, conn: Connection, google_token: str) -> dict:
        claims = await self.verify_google_token(google_token)
        user = await self.get_or_create_user(conn, claims["email"], claims.get("name", ""))
        if not user["is_active"]:
            raise AuthenticationError(detail="User account is deactivated")
        await conn.execute("UPDATE users SET last_login_at = NOW() WHERE id = $1", user["id"])
        # par M1 — family nova por login (per-device), igual ao password path do auth-hardened
        refresh_token, family = await jwt_service.create_refresh_token(conn, user_id=user["id"])
        access_token = jwt_service.create_access_token(sub=str(user["id"]), family=family)
        return {"user": user, "access_token": access_token, "refresh_token": refresh_token}

    async def get_or_create_user(self, conn: Connection, email: str, name: str) -> dict:
        user = await user_repository.get_user_by_email(conn, email)
        if user:
            return user
        # username único derivado do email; OAuth users não têm senha utilizável
        base = email.split("@")[0]
        username, counter = base, 1
        while await user_repository.get_user_by_username(conn, username):
            username, counter = f"{base}{counter}", counter + 1
        return await user_repository.create_user(
            conn,
            User(
                username=username, email=email, name=name,
                password_hash="oauth_no_password", is_active=True, created_by="google",
            ),
        )


google_oauth_service = GoogleOAuthService()
```

## 5. Backend — rota `POST /api/v1/auth/google`

```python
# api/routes/auth/auth.py  (router = APIRouter(prefix="/auth"))
@router.post("/google", response_model=TokenResponse, summary="Google Login")
async def google_login(
    response: Response, body: GoogleLoginRequest, conn: Connection = Depends(get_conn)
) -> TokenResponse:
    id_token_str = await google_oauth_service.exchange_code_for_id_token(body.code, body.redirect_uri)
    result = await google_oauth_service.authenticate_with_google(conn, id_token_str)
    apply_auth_refresh_cookie(response, result["refresh_token"])  # auth-hardened §7
    return TokenResponse(access_token=result["access_token"], user=result["user"])
```

Refresh sempre via cookie HttpOnly (`auth-hardened` §7), nunca no JSON. Login fica sob `/auth`,
junto de `/auth/token`. Centralizer crava `APIRouter(prefix=API_V1_PREFIX)` → `/api/v1/auth/google`.

## 6. Frontend — `GoogleSignInButton` (popup auth-code)

`bun add @react-oauth/google`. Componente em `components/ui/google-signin-button.tsx` (kebab-case,
pasta canônica — NÃO em `components/auth/`).

```tsx
// components/ui/google-signin-button.tsx
import { GoogleOAuthProvider, useGoogleLogin } from "@react-oauth/google";
import { Loader2 } from "lucide-react";
import { FcGoogle } from "react-icons/fc";
import { Button } from "@/components/ui/button";

interface GoogleSignInButtonProps {
  onSuccess: (code: string) => void;
  onError?: (error: string) => void;
  loading?: boolean;
  className?: string; // permite botão maior quando Google é primário (ex.: "h-11")
}

function Inner({
  onSuccess,
  onError,
  loading,
  className,
}: GoogleSignInButtonProps) {
  // auth-code: o popup devolve um `code` curto. O backend troca por id_token (com o secret).
  const login = useGoogleLogin({
    flow: "auth-code",
    onSuccess: ({ code }) =>
      code ? onSuccess(code) : onError?.("Sem authorization code"),
    onError: () => onError?.("Falha no login com Google"),
  });
  return (
    <Button
      type="button"
      variant="outline"
      className={className ?? "w-full"}
      disabled={loading}
      onClick={() => login()}
    >
      {loading ? (
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      ) : (
        <FcGoogle className="mr-2 h-4 w-4" />
      )}
      {loading ? "Autenticando..." : "Continuar com Google"}
    </Button>
  );
}

export function GoogleSignInButton(props: GoogleSignInButtonProps) {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  if (!clientId) {
    props.onError?.("Google OAuth não configurado");
    return null;
  }
  return (
    <GoogleOAuthProvider clientId={clientId}>
      <Inner {...props} />
    </GoogleOAuthProvider>
  );
}
```

## 7. Frontend — service + hook + página

```typescript
// lib/api/services/auth.ts — envia o code; redirectUri="postmessage" casa com o popup
async googleLogin(code: string): Promise<AuthResponse> {
  const res = await this.client.post<AuthResponse>("/auth/google", { code, redirectUri: "postmessage" });
  const data = res?.data ?? res;
  if (data?.accessToken) setAccessToken(data.accessToken); // M1: memória (auth-hardened §9)
  return data;
}
```

```typescript
// hooks/useAuth.ts — mutation googleLogin
const googleLoginMutation = useMutation({
  mutationFn: (code: string) => auth.googleLogin(code),
});
// exporta: googleLogin, googleLoginAsync, isGoogleLoggingIn, googleLoginError
```

**Layout da página de login** — duas formas, escolha pela política do projeto:

- **Google-only** (sem senha): só `<GoogleSignInButton />` (full-width), sem form, sem link de signup.
- **Dual-mode** (Google + email): Google **primário no topo** (`className="h-11"`, maior) → divider
  "ou entrar com email" → form username/senha embaixo. Google em cima porque é o caminho preferido.

```tsx
<GoogleSignInButton
  className="h-11 w-full"
  loading={isGoogleLoggingIn}
  onSuccess={async (code) => {
    await googleLoginAsync(code);
    navigate({ to: postLoginTarget });
  }}
/>
```

## 8. Contrato portável (language-agnostic — Axum / Fiber)

O backend é o mesmo em qualquer linguagem; replicar = traduzir estes 4 passos.

```
INPUT:    POST /api/v1/auth/google   body { code, redirect_uri="postmessage" }
STEP 1 exchange: POST https://oauth2.googleapis.com/token
                 (code, client_id, client_secret, redirect_uri, grant_type=authorization_code) -> id_token
STEP 2 verify:   valida id_token via JWKS do Google: assinatura + iss∈{accounts.google.com,
                 https://accounts.google.com} + aud==client_id + exp + email_verified
STEP 3 identity: get-or-create user por email (claims: sub, email, name, picture)
STEP 4 session:  M1 — access JWT curto (iss/aud/sub/fam/jti) + refresh opaco (family + SHA-256)
                 em cookie HttpOnly SameSite=Strict path-scopado
OUTPUT:   { access_token, user } no JSON  +  refresh no cookie (NUNCA no body)
SECRETS:  client_secret em .env;  client_id público (yaml + JS bundle)
CONSOLE:  só Authorized JavaScript origins (popup);  redirect URIs só se migrar p/ redirect-callback
```

## Don'ts

- **NUNCA** confiar no id_token/`code` sem re-verificar no backend (JWKS + aud + iss + email_verified).
- **NUNCA** cadastrar Authorized redirect URI no Console p/ o fluxo popup — é config morta.
- **NUNCA** persistir access token em `localStorage`/`sessionStorage`/Zustand persist — só memória (M1).
- **NUNCA** retornar refresh token no JSON — só cookie HttpOnly (`auth-hardened` §7).
- **NUNCA** login sob `/accounts/auth/google` — canônico é `/api/v1/auth/google` (login = `auth`).
- **NUNCA** `client_secret` no yaml/bundle — só `.env`. `client_id` é público, vai no yaml.
- **NUNCA** flag `GOOGLE_LOGIN_ENABLED` quando Google é o único login (flag só p/ coexistência).
- **NUNCA** `GoogleSignInButton` em `components/auth/` — canônico é `components/ui/`.
- **NUNCA** verificar via `GET /oauth2/v3/userinfo` — sempre `id_token.verify_oauth2_token` (`auth-hardened` §6).
- **NUNCA** `redirect_uri` divergente entre front e backend — ambos `"postmessage"` no popup.
