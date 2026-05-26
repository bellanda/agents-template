---
name: auth-hardened
description: Padrão de autenticação hardened cross-projeto — JWT access curto com claims iss/aud/fam/jti, refresh opaco com family+used+SHA-256, JTI denylist por family em Valkey, Argon2id OWASP RFC 9106 §4, Google OAuth via id_token + JWKS, cookie HttpOnly path-scopado SameSite=Strict, access token em memória no frontend, BroadcastChannel + Web Locks API para refresh concurrency-safe. INVOCAR ANTES de escrever ou alterar qualquer endpoint /auth/*, repository de refresh_tokens, middleware de auth, login/logout/refresh flow, configuração de cookies, Google OAuth handler, password hashing, ou qualquer feature que toque access/refresh tokens. Complementa as seções `## Auth` em `backend.md` e `frontend.md` (rules são os invariantes; aqui está a implementação completa).
---

# Auth Hardened — Implementação de Referência

Stack: PyJWT (HS256) + Argon2-cffi + asyncpg + Valkey + google-auth (id_token+JWKS). Frontend: memória + cookie HttpOnly + BroadcastChannel + Web Locks API. Pareado com rules `backend.md > Auth` e `frontend.md > Auth`.

## 1. Tabela `refresh_tokens` (dbmate)

```sql
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    family      UUID NOT NULL DEFAULT gen_random_uuid(),
    used        BOOLEAN NOT NULL DEFAULT false,
    token_hash  CHAR(64) NOT NULL,                         -- SHA-256 hex
    revoked_at  TIMESTAMPTZ NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ux_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX ix_refresh_tokens_family_active
    ON refresh_tokens(family) WHERE revoked_at IS NULL;
CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens(user_id);
```

## 2. Access token — encode/decode

`sub` (user), `fam` (UUID da family de refresh — herdada pelos rotacionados), `jti` (UUID4 único), `iss`, `aud`, `exp`, `iat`, `token_type="Bearer"`.

```python
import jwt, secrets, time, uuid

REQUIRED_CLAIMS = ["sub", "fam", "jti", "iss", "aud", "exp", "iat"]

def create_access_token(*, sub: str, family: uuid.UUID, ttl_seconds: int) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "fam": str(family),
            "jti": str(uuid.uuid4()),
            "iss": settings.jwt.issuer,
            "aud": settings.jwt.audience,
            "iat": now,
            "exp": now + ttl_seconds,
            "token_type": "Bearer",
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt.algorithm,  # HS256
    )

def verify_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt.algorithm],
        issuer=settings.jwt.issuer,
        audience=settings.jwt.audience,
        leeway=settings.jwt.leeway_seconds,
        options={"require": REQUIRED_CLAIMS},
    )
```

**NUNCA** `algorithms=[...]` com lista. **NUNCA** decode sem `options={"require": [...]}` + `issuer=` + `audience=`. PyJWT já valida tudo nativamente.

## 3. Refresh token — opaco + family rotation

```python
import hashlib, secrets

def generate_opaque_refresh_token() -> str:
    return secrets.token_urlsafe(64)

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

Rotation flow (em `auth_service.refresh_access_token`):

```python
async def refresh_access_token(conn, raw_refresh: str) -> TokenPair:
    digest = hash_refresh_token(raw_refresh)
    row = await refresh_token_repository.find_by_token_hash(conn, digest)
    if row is None:
        raise AuthenticationError("invalid_refresh")

    # Replay attack — reuso de token já usado: revoga a family inteira
    if row["used"]:
        await refresh_token_repository.revoke_family(conn, row["family"])
        await deny_family(row["family"])
        raise AuthenticationError("replay_detected")

    if row["revoked_at"] is not None or row["expires_at"] < datetime.now(UTC):
        raise AuthenticationError("refresh_expired")

    # Caminho normal: marca usado, gera próximo
    await refresh_token_repository.mark_used(conn, row["id"])
    return await _issue_tokens(conn, user_id=row["user_id"], family=row["family"])
```

`_issue_tokens(family=None)`: se `family is None`, gera UUID novo (login fresh); senão herda (refresh). Insere `refresh_tokens` com `token_hash = sha256(novo)`, retorna pair `(access_jwt, refresh_opaque)`.

## 4. JTI denylist por family em Valkey

Key: `denylist:family:{family_uuid}` · Value: `b"1"` · TTL: `JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60`.

```python
async def deny_family(family: uuid.UUID) -> None:
    valkey = get_valkey()
    ttl = int(settings.jwt.access_token_expire_minutes * 60)
    await valkey.setex(f"denylist:family:{family}", ttl, b"1")

async def is_family_denied(family: uuid.UUID) -> bool:
    valkey = get_valkey()
    return await valkey.exists(f"denylist:family:{family}") == 1
```

Middleware de auth, depois de `verify_access_token`:

```python
claims = verify_access_token(token)
family = uuid.UUID(claims["fam"])
if await is_family_denied(family):
    raise AuthenticationError("token_revoked")
```

Família como chave (não JTI) porque o access novo emitido pelo `/refresh` herda a mesma family — logout invalida access + futuros refreshes em um único write. ~50μs em UDS.

## 5. Argon2id — params OWASP RFC 9106 §4

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

password_hasher = PasswordHasher(
    time_cost=3,            # iterações
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=4,
)

# Test override
if os.getenv("ARGON2_FAST") == "1":
    password_hasher = PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1)
```

Login com `verify_and_update` para rehash automático quando params mudarem:

```python
async def authenticate(conn, email: str, password: str) -> dict:
    user = await user_repository.find_by_email(conn, email)
    if user is None or user["password_hash"] is None:
        raise AuthenticationError("invalid_credentials")
    try:
        new_hash = password_hasher.verify_and_update(user["password_hash"], password)
        if new_hash is not None:
            await user_repository.update_password_hash(conn, user["id"], new_hash)
    except VerifyMismatchError:
        raise AuthenticationError("invalid_credentials")
    return user
```

## 6. Google OAuth — id_token + JWKS

NUNCA `GET /oauth2/v3/userinfo` com bearer access (rede + parsing manual). Use a lib oficial — valida `iss`, `aud`, `exp`, assinatura via JWKS público com cache automático:

```python
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

def verify_google_id_token(id_token_str: str) -> dict:
    claims = id_token.verify_oauth2_token(
        id_token_str,
        google_requests.Request(),
        audience=settings.google.oauth_client_id,
    )
    if not claims.get("email_verified"):
        raise AuthenticationError("email_not_verified")
    return claims  # ["sub"] = Google user_id, ["email"], ["name"], ["picture"]
```

Frontend já entrega `credential` (id_token JWT) do `<GoogleSignInButton>` — backend só verifica.

## 7. Cookie de refresh

```python
def apply_auth_refresh_cookie(response: Response, refresh_token: str, ttl_seconds: int) -> None:
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=settings.cookies.secure,           # false só em local plain HTTP
        samesite="strict",                        # never "lax"/"none"
        path=f"{settings.api.v1_prefix}/auth/token",  # cookie viaja só pra /refresh
        max_age=ttl_seconds,
    )

def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("refresh_token", path=f"{settings.api.v1_prefix}/auth/token")
```

Path scopado em `/api/v1/auth/token` elimina o cookie de 99% dos requests. SameSite=Strict é seguro porque login/refresh são same-origin via NGINX em prod.

## 8. Routes contract

| Route                            | Body                | Sets cookie | Returns                          |
| -------------------------------- | ------------------- | ----------- | -------------------------------- |
| `POST /auth/token`               | `{email,password}` ou `{id_token}` | ✓ refresh | `{access_token, user}`          |
| `POST /auth/token/refresh`       | — (cookie só)       | ✓ refresh   | `{access_token}`                 |
| `POST /auth/session/logout`      | —                   | clear       | `204`                            |

Logout revoga a family inteira (`refresh_token_repository.revoke_family(conn, family)`) + `deny_family(family)` no Valkey. Outras sessions do user em outros devices continuam vivas.

**Defensive `_strip_refresh`:** em `/auth/token` (login), o handler deve remover qualquer campo `refresh_token` do request body — refresh nunca aparece em JSON, só em cookie.

## 9. Frontend — access em memória

```typescript
// lib/api/access-token-store.ts
let accessToken: string | null = null;
const CHANNEL_NAME = "<project>-auth";  // namespaced (kailos-auth, balizap-auth, ...)
const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel(CHANNEL_NAME) : null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  channel?.postMessage({ token });
}

channel?.addEventListener("message", (e) => {
  accessToken = e.data?.token ?? null;
});
```

**NUNCA** `localStorage.setItem("access_token", ...)`. XSS = jogo perdido se access vive em storage acessível.

## 10. Frontend — bootstrap (mount do app)

```typescript
// lib/auth/use-bootstrap.ts
export function useBootstrap() {
  const [isReady, setIsReady] = useState(false);
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/v1/auth/token/refresh", {
          method: "POST",
          credentials: "include",
        });
        if (res.ok) {
          const { access_token } = await res.json();
          setAccessToken(access_token);
        }
      } finally {
        setIsReady(true);
      }
    })();
  }, []);
  return { isReady };
}

// main.tsx
function AppRoot() {
  const { isReady } = useBootstrap();
  if (!isReady) return null;            // ou splash
  return <RouterProvider router={router} />;
}
```

Sem flash de "logado vira deslogado" — router só monta após `/refresh` resolver.

## 11. Frontend — refresh on 401 (Web Locks API)

```typescript
// lib/api/refresh-lock.ts
async function withRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  if (typeof navigator !== "undefined" && navigator.locks) {
    return navigator.locks.request("auth:refresh", { mode: "exclusive" }, fn);
  }
  return fn();  // fallback: mesma tab, single-threaded JS
}

// ApiClient.fetch interceptor
async function fetchWithAuth(url: string, init: RequestInit): Promise<Response> {
  let res = await fetch(url, withAuthHeader(init));
  if (res.status === 401 && url !== REFRESH_URL) {
    const refreshed = await withRefreshLock(refreshAccessToken);
    if (refreshed) res = await fetch(url, withAuthHeader(init));
  }
  return res;
}
```

3 requests racing num 401 = 1 chamada ao `/refresh`, os outros esperam o lock.

## 12. Frontend — login + logout

```typescript
const useLogin = () =>
  useMutation({
    mutationFn: async ({ email, password }: LoginPayload) => {
      const res = await api.post<TokenResponse>("/api/v1/auth/token", { email, password });
      setAccessToken(res.data.access_token);     // BroadcastChannel propaga
      return res.data.user;
    },
  });

const useLogout = () =>
  useMutation({
    mutationFn: () => api.post("/api/v1/auth/session/logout"),
    onSuccess: () => {
      setAccessToken(null);                       // BroadcastChannel propaga
      queryClient.clear();
      router.navigate({ to: ROUTE_PATHS.LOGIN });
    },
  });
```

## 13. Config & secrets

YAML (`config/app/{env}.yaml`):

```yaml
jwt:
  algorithm: HS256
  issuer: <project>-api
  audience: <project>-web
  access_token_expire_minutes: 15
  refresh_token_expire_days: 7
  leeway_seconds: 5
cookies:
  secure: false   # local | true em staging/prod
google:
  oauth_client_id: "<google-client-id>"  # onde aplicável
```

`.env`:
- `JWT_SECRET_KEY` (obrigatório, `secrets.token_hex(32)`)
- `VALKEY_PASSWORD` (obrigatório em docker, opcional em pure-host)
- `GOOGLE_OAUTH_CLIENT_SECRET` (onde aplicável)

## 14. Don'ts

- **NUNCA** JWT no refresh — opaco only (`token_urlsafe(64)`).
- **NUNCA** plain text de refresh no DB — só SHA-256 hex (CHAR(64)).
- **NUNCA** persistir access em browser storage. Único caminho aceitável é memória.
- **NUNCA** decode JWT sem `options={"require": [...]}` + `issuer=` + `audience=`.
- **NUNCA** `algorithms=[...]` com lista no decode — sempre `[settings.jwt.algorithm]`.
- **NUNCA** Google OAuth via `/userinfo` — sempre `id_token.verify_oauth2_token`.
- **NUNCA** logout que só apaga cookie sem revogar family + `deny_family` no Valkey.
- **NUNCA** Argon2 com params default — sempre OWASP RFC 9106 §4 (t=3, m=64MiB, p=4).
- **NUNCA** `cookie path="/"` — sempre `/api/v1/auth/token`.
- **NUNCA** `SameSite=lax/none` — sempre `strict` (same-origin via NGINX).
- **NUNCA** `/refresh` em paralelo sem `withRefreshLock`.
- **NUNCA** `persist` em Zustand auth store.
- **NUNCA** redirect manual no 401 — interceptor retenta com refresh primeiro.
- **NUNCA** refresh token em JSON body — backend strip defensivo + cookie só.
