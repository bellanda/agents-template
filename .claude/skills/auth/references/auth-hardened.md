> Reference do gate `auth` (core: sessão, JWT access+refresh, family rotation, cookie HttpOnly, Argon2id). Implementação completa.

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

**Claim atômico (fecha o TOCTOU).** NUNCA `find` seguido de `mark_used` — dois refreshes concorrentes com o mesmo token passariam ambos pelo check. Um único `UPDATE ... WHERE used=false` row-locka a linha: só um vence, o segundo casa 0 linhas e recebe `None`.

```python
async def claim_if_unused(conn, token_hash: str) -> dict | None:
    row = await conn.fetchrow(
        """
        UPDATE refresh_tokens SET used = true
        WHERE token_hash = $1 AND used = false AND revoked_at IS NULL
        RETURNING *
        """,
        token_hash,
    )
    return dict(row) if row else None
```

Rotation flow (em `auth_service.refresh_access_token`). O miolo "cunhar par + responder" fica num helper `_issue_rotated_pair` reusado pelo caminho normal E pela recuperação por graça (§3a); ambos aplicam o teto absoluto, o check de usuário ativo, e o GC (§3b):

```python
async def refresh_access_token(conn, raw_refresh: str) -> TokenPair:
    digest = hash_refresh_token(raw_refresh)

    # Caminho normal: reivindica atomicamente e rotaciona.
    claimed = await refresh_token_repository.claim_if_unused(conn, digest)
    if claimed is not None:
        return await _issue_rotated_pair(conn, claimed)

    row = await refresh_token_repository.find_by_token_hash(conn, digest)
    if row is None:
        raise AuthenticationError("invalid_refresh")     # nunca existiu / já coletado
    if row["revoked_at"] is not None:
        raise AuthenticationError("family_dead")          # família já morta

    # Token `used` mas família viva → pode ser Set-Cookie perdido logo após a
    # rotação (§3a). Fora da graça, é replay genuíno: queima a família inteira.
    recovered = await _try_grace_recovery(conn, row)      # §3a; None se não elegível
    if recovered is not None:
        return recovered

    await refresh_token_repository.revoke_family(conn, row["family"])
    await deny_family(row["family"])
    raise AuthenticationError("replay_detected")
```

`_issue_rotated_pair(conn, claimed)`: valida `expires_at`, aplica o teto absoluto (`family_created_at + absolute_lifetime`), checa `user.is_active`, insere o novo `refresh_tokens` herdando `family` + `family_created_at` (`token_hash = sha256(novo)`), aquece o auth-context, roda o GC (§3b), e retorna o pair `(access_jwt, refresh_opaque)`.

## 3a. Janela de graça de reuso — recupera o Set-Cookie perdido

Rotacionar a cada refresh (a cada 5–30 min) tem uma corrida residual: se o `Set-Cookie` do token novo se perde (resposta não entregue após o commit da rotação, multi-tab), o browser mantém o token ANTIGO — agora `used=true`. Sem tratamento, o próximo refresh dispara a detecção de replay e **queima a família** → relogin forçado. A janela de graça recupera esse caso benigno.

```python
async def _try_grace_recovery(conn, row: dict) -> TokenPair | None:
    head = await refresh_token_repository.find_active_head_for_family(conn, row["family"])
    if head is None:
        return None
    grace = dt.timedelta(seconds=auth_config.REFRESH_REUSE_GRACE_SECONDS)  # default 20s
    if dt.datetime.now(dt.UTC) - head["created_at"] > grace:
        return None
    # UMA tentativa atômica de reivindicar o head. Se perder a corrida pra um
    # concorrente, retorna None → cai no replay genuíno (sem retry = sem ping-pong).
    recovered = await refresh_token_repository.claim_if_unused(conn, head["token_hash"])
    if recovered is None:
        return None
    log.info("refresh_grace_recovery", family=str(row["family"]), user_id=row["user_id"])
    return await _issue_rotated_pair(conn, recovered)
```

`find_active_head_for_family`: `SELECT * ... WHERE family=$1 AND used=false AND revoked_at IS NULL LIMIT 1` — acha o head vivo sem nunca precisar do valor cru (o DB só guarda o SHA-256).

> **Trade-off de segurança:** um atacante que roube um refresh e o apresente dentro de `REFRESH_REUSE_GRACE_SECONDS` da última rotação é recuperado em silêncio em vez de disparar a revogação. Isso estreita a janela de detecção de roubo de "sempre" para "exceto na corrida curta logo após cada rotação". Por isso a janela é curta (10–30s), tunável por env, e **nunca** deve virar um TTL de cache.

## 3b. GC de linhas mortas — mantém a tabela enxuta sem `used_at`

Chamado no fim de toda rotação bem-sucedida (dentro de `_issue_rotated_pair`). Deleta linhas do usuário que sejam revogadas (qualquer idade), naturalmente expiradas, OU `used=true` cujo **sucessor** (irmão mais novo da mesma família) já passou de `REFRESH_GC_RETENTION_SECONDS` (default **3600s** — muito maior que a graça, para nunca competir com ela).

```sql
DELETE FROM refresh_tokens t
WHERE t.user_id = $1
  AND (
        t.revoked_at IS NOT NULL
        OR t.expires_at < now()
        OR (t.used = true AND EXISTS (
              SELECT 1 FROM refresh_tokens s
              WHERE s.family = t.family
                AND s.created_at > t.created_at
                AND s.created_at < now() - ($2 * INTERVAL '1 second')))
      )
```

Por que gatar no `created_at` do **sucessor** e não no da própria linha: o `created_at` do sucessor marca quando ESTA linha virou `used`. Um head pode ficar `used=false` por horas de inatividade antes de rotacionar; gatar no `created_at` da própria linha superestimaria a idade e deletaria uma linha recém-superada — ressuscitando o bug de replay perdido. Steady state: ~2–3 linhas por família (head + os usados dentro da janela de detecção).

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
def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("refresh_token", path=f"{settings.api.v1_prefix}/auth/token")

def apply_auth_refresh_cookie(response: Response, refresh_token: str, ttl_seconds: int) -> None:
    # Clear-then-set: limpa antes de setar para o browser nunca carregar um cookie
    # stale/duplicado com atributos divergentes. Só o valor recém-rotacionado
    # sobrevive. Emite 2 Set-Cookie (delete + set) — legal em HTTP, o último vence.
    clear_auth_cookies(response)
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=settings.cookies.secure,           # false só em local plain HTTP
        samesite="strict",                        # never "lax"/"none"
        path=f"{settings.api.v1_prefix}/auth/token",  # cookie viaja só pra /refresh
        max_age=ttl_seconds,
    )
```

Path scopado em `/api/v1/auth/token` elimina o cookie de 99% dos requests. SameSite=Strict é seguro porque login/refresh são same-origin via NGINX em prod. O clear-then-set fecha a causa-raiz de "cookie do browser diverge do banco": todo login/Google/refresh limpa-antes-de-setar sem depender de cada rota lembrar. Testes que leem o header `Set-Cookie` devem pegar o **último** `refresh_token=` (agora são 2).

## 8. Routes contract

| Route                            | Body                | Sets cookie | Returns                          |
| -------------------------------- | ------------------- | ----------- | -------------------------------- |
| `POST /auth/token`               | `{email,password}` ou `{id_token}` | ✓ refresh | `{access_token, user}`          |
| `POST /auth/token/refresh`       | — (cookie só)       | ✓ refresh   | `{access_token}`                 |
| `POST /auth/session/logout`      | —                   | clear       | `204`                            |

Logout revoga a family inteira (`refresh_token_repository.revoke_family(conn, family)`) + `deny_family(family)` no Valkey. Outras sessions do user em outros devices continuam vivas.

**Logout SEMPRE limpa os cookies — nunca 401 antes de limpar.** Se o cookie de refresh está ausente/desconhecido/revogado (o próprio caso de dessincronia que motiva este hardening), o handler ainda tem que responder 200 e emitir o header de clear. Forma canônica:

```python
async def session_logout(request, response, conn) -> MessageResponse:
    refresh = request.cookies.get("refresh_token")
    if refresh:
        with contextlib.suppress(AuthenticationError):
            await auth_service.end_session_by_refresh_token(conn, refresh)
    clear_auth_cookies(response)          # sempre, mesmo sem cookie
    return MessageResponse(message="Logged out successfully")
```

**Defensive `_strip_refresh`:** em `/auth/token` (login), o handler deve remover qualquer campo `refresh_token` do request body — refresh nunca aparece em JSON, só em cookie.

## 8b. Login revoga a família anterior — conciliação browser ↔ Postgres

Cunhar uma família nova sem matar a que veio no cookie deixa a antiga **viva no banco** enquanto o browser já esqueceu dela. É a dessincronia que produz "loguei de novo e bugou": duas famílias vivas, uma delas sem dono.

```python
async def reset_session_from_cookie(self, conn, refresh_token: str | None) -> None:
    """Revoga a família do cookie ANTES de cunhar a nova. É `end_session_by_refresh_token`
    SEM o raise quando a linha não existe: cookie ausente, expirado, de outro app ou já
    revogado é no-op silencioso. Login NUNCA falha por causa da limpeza."""
    if not refresh_token:
        return
    row = await refresh_token_repository.find_by_token_hash(conn, hash_refresh_token(refresh_token))
    if not row:
        return
    await refresh_token_repository.revoke_family(conn, row["family"])
    await deny_family(str(row["family"]))          # mata os access in-flight antes do exp
    log.info("session_reset_on_login", family=str(row["family"]))
```

Chamado no handler de login **antes** de emitir o par novo.

**Onde isso NÃO alcança:** o cookie é path-scopado em `/api/v1/auth/token` (§7), então `POST /auth/google` — que vive fora desse path — **nunca o recebe**; escrever a chamada lá é código morto. Nesse caso a revogação é um **handshake do cliente**: `POST /auth/token/logout` (a única rota que enxerga o cookie) e só então o login. Vale a regra do §8: o logout limpa e responde 200 mesmo sem cookie válido, então o handshake é sempre seguro.

Resultado esperado, e o que o teste tem que provar: **uma família viva por dispositivo**, sempre — inclusive depois de N logins seguidos e ao trocar de conta no mesmo browser.

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

## 10. Frontend — bootstrap gate (o router monta DEPOIS da sessão decidir)

O `authStore` expõe `status: "pending" | "authenticated" | "anonymous"` e um `ready` que resolve **uma vez**, quando o bootstrap assenta. Sem timers, sem polling, sem `CustomEvent` como canal de coordenação.

```typescript
class AuthStore {
  private status: AuthStatus = "pending";
  readonly ready: Promise<void>;                    // resolvido pelo bootstrap, 1×

  getState() {
    return { user: this.user, isAuthenticated: this.status === "authenticated",
             isLoading: this.status === "pending", status: this.status };
  }
  setState(s) { …; if (this.status !== "pending") this.markReady(); this.notify(); }
}

// main.tsx — o gate
function AppRouter() {
  const { isLoading } = useDataProvider();          // espelha o authStore
  if (isLoading) return <Splash />;                 // NUNCA <RouterProvider> aqui
  return <RouterProvider router={router} />;
}
```

O bootstrap tem duas formas equivalentes — **ou** `refreshToken()` explícito e depois `/accounts/me`, **ou** `/accounts/me` direto (sai sem Bearer, toma 401, o interceptor do §11 roda `/auth/token` com o cookie e repete). Escolha uma por projeto e mantenha; a segunda gasta um round-trip a mais no cold start e **duas** chamadas a `/accounts/me` — o que muda a asserção dos testes.

**Por que o gate:** com o router montado antes, um `beforeLoad` roda com `isLoading` ainda `true` e manda usuário autenticado pro `/login` — só F5 recupera. É o sintoma nº 1 em celular/3G. O `beforeLoad` fica **síncrono** (lê `getState()`, `throw redirect(...)`), sem `await`, sem fetch, sem `waitForAuthCheck` com deadline.

**Resume de background** (crítico no iOS, que congela a WebView do PWA instalado): ao voltar de um período REAL em background (~60s), revalida a sessão pelo mesmo caminho do bootstrap, em vez de esperar o próximo 401. Troca rápida de aba não pode custar round-trip.

```typescript
useEffect(() => {
  let hiddenAt = 0;
  const onVisibility = () => {
    if (document.hidden) { hiddenAt = Date.now(); return; }
    if (!hiddenAt || Date.now() - hiddenAt < RESUME_REVALIDATE_AFTER_MS) return;
    hiddenAt = 0;
    if (!authStore.getState().isAuthenticated) return;
    fetchCurrentUser();
  };
  document.addEventListener("visibilitychange", onVisibility);
  return () => document.removeEventListener("visibilitychange", onVisibility);
}, [fetchCurrentUser]);
```

**Só 401/403 encerram a sessão.** O `catch` do bootstrap/resume tem que ramificar no status — falha de rede (`status === 0`) e 5xx **mantêm** a sessão que já existe e só encerram o `isLoading`:

```typescript
} catch (error: unknown) {
  const status = error && typeof error === "object" && "status" in error
    ? (error as { status: number }).status : 0;
  if (status === 401 || status === 403) { /* … refresh, e só então derruba … */ }
  else {
    // Rede caiu ≠ sessão inválida. O refresh em cookie continua válido.
    const { user } = authStore.getState();
    if (user) return authStore.setState({ user, isAuthenticated: true, isLoading: false });
    …
  }
}
```

Um `catch {}` cego aqui é o bug do **resume sem sinal**: o celular volta do metrô/elevador, o `/accounts/me` do resume falha por rede, o app derruba o token e joga no `/login` quem só perdeu a conexão — com o cookie de refresh intacto. O que o usuário vê disso é a mensagem de rede em pt-BR do `ApiClient` (`rules/frontend.md > API Layer`), **não** um logout.

## 11. Frontend — refresh on 401 (Web Locks API)

```typescript
// lib/api/refresh-lock.ts
async function withRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  if (typeof navigator !== "undefined" && navigator.locks) {
    return navigator.locks.request("auth:refresh", { mode: "exclusive" }, fn);
  }
  return fn();  // fallback: mesma tab, single-threaded JS
}

// ApiClient — o guard é o SNAPSHOT PRÉ-LOCK, nunca "já existe token"
async function handleTokenRefresh(): Promise<boolean> {
  const tokenBeforeLock = getAccessToken();
  return withRefreshLock(async () => {
    // Quem esperou o lock não repete a rotação: se o token MUDOU enquanto
    // aguardávamos, outro caller/aba já trouxe o par novo.
    const current = getAccessToken();
    if (current && current !== tokenBeforeLock) return true;
    …POST /auth/token (grant_type=refresh_token, credentials: "include")…
  });
}

async function fetchWithAuth(url: string, init: RequestInit, retryCount = 0): Promise<Response> {
  let res = await fetch(url, withAuthHeader(init));
  if (res.status === 401 && retryCount === 0 && !isAuthRoute(url)) {
    if (await handleTokenRefresh()) res = await fetch(url, withAuthHeader(init));
  }
  return res;
}
```

3 requests racing num 401 = 1 chamada ao `/auth/token`, os outros esperam o lock.

**`if (getAccessToken()) return true;` é BUG, não otimização.** O access expirado continua em memória e é truthy — o guard pula o refresh e o retry sai com o token morto. Sintoma exato: "adicionei algo num CRUD simples, deu erro, F5 e aí funcionou". A comparação certa é contra o snapshot tirado ANTES de pegar o lock.

**Todo caller de refresh disputa o MESMO lock** — o interceptor de 401 e o `AuthService.refreshToken()` do bootstrap. Dois caminhos postando `/auth/token` ao mesmo tempo é lido como reuso pela rotação `family+used` (§3), que revoga a família inteira e derruba a sessão. Flag `isRefreshing` de instância não resolve: não serializa entre abas nem entre instâncias do client.

`retryCount === 0` + `isAuthRoute` fecham o loop: 401 na própria rota de auth não dispara refresh.

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

## 12b. Login = reset total de sessão (browser + Postgres)

Todo login — bem-sucedido ou não, mesmo usuário ou outro — parte de estado zero. Nada da sessão anterior sobrevive, nem no browser nem no banco. O erro comum é fazer isso só no logout: aí o cache do usuário A sobrevive ao login do B, e a família de A continua viva no Postgres.

| #   | Onde                          | Passo                                                              |
| --- | ----------------------------- | ------------------------------------------------------------------ |
| 1   | front, **antes** de chamar    | `setAccessToken(null)` — o access velho não participa do login      |
| 2   | front, **antes** de chamar    | `queryClient.clear()` — o cache do usuário anterior morre aqui      |
| 3   | back, **antes** de cunhar     | revoga a família do refresh que veio no cookie (§8b)                |
| 4   | back, **antes** de cunhar     | `deny_family` no Valkey — mata os access in-flight antes do `exp`   |
| 5   | back                          | cunha o par novo                                                    |
| 6   | back                          | `apply_auth_refresh_cookie` (clear-then-set, §7)                    |
| 7   | front, no sucesso             | semeia o user novo no cache **já limpo**                            |

```typescript
const useGoogleLogin = () =>
  useMutation({
    mutationFn: async (code: string) => {
      setAccessToken(null);              // 1
      queryClient.clear();               // 2
      await auth.endServerSession();     // 3–4 via handshake (§8b); best-effort, nunca lança
      return auth.googleLogin(code);     // 5–6
    },
    onSuccess: (user) => queryClient.setQueryData(["auth", "user"], user),  // 7
    onError: () => { setAccessToken(null); queryClient.clear(); },          // falhou = limpo, não meio-logado
  });
```

Os passos 1–2 vão no `mutationFn`, **não** no `onSuccess`: semear por cima de um cache antigo não é limpar. `endServerSession()` engole 401/rede fora — a limpeza é best-effort e não pode impedir o login.

## 13. Config & secrets

YAML (`config/app/{env}.yaml`):

```yaml
jwt:
  algorithm: HS256
  issuer: <project>-api
  audience: <project>-web
  access_token_expire_minutes: 15
  refresh_token_expire_days: 30       # explícito nos 3 envs — trivial de alterar
  absolute_refresh_lifetime_days: 60  # teto absoluto da família (não desliza)
  leeway_seconds: 5
  refresh_reuse_grace_seconds: 20     # §3a — janela de recuperação (10–30s)
  refresh_gc_retention_seconds: 3600  # §3b — retenção antes do GC (>> graça)
cookies:
  secure: false   # local | true em staging/prod
google:
  oauth_client_id: "<google-client-id>"  # onde aplicável
```

Deixe `refresh_token_expire_days` + os 2 knobs **explícitos nos 3 envs** (não só no default Pydantic) — o operador edita o TTL num lugar óbvio. `refresh_reuse_grace_seconds`/`refresh_gc_retention_seconds` têm default no `JwtSettings` (20/3600) para um yaml legado sem as chaves não quebrar.

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
- **NUNCA** raise (401) antes de limpar os cookies no logout — logout SEMPRE limpa e retorna 200, mesmo com refresh ausente/desconhecido/revogado (§8).
- **NUNCA** `find` + `mark_used` separados na rotação — só o `claim_if_unused` atômico (§3). O par não-atômico deixa dois refreshes concorrentes cunharem tokens (TOCTOU).
- **NUNCA** setar o cookie de refresh sem limpar antes — `apply_auth_refresh_cookie` faz clear-then-set (§7), senão o browser diverge do banco (a causa-raiz do relogin).
- **NUNCA** deletar `used=true` no GC sem checar o `created_at` do SUCESSOR dentro de retention (§3b) — gatar no `created_at` da própria linha deleta uma linha recém-superada e ressuscita o replay perdido.
- **NUNCA** alargar `REFRESH_REUSE_GRACE_SECONDS` além de 10–30s nem tratá-lo como TTL de cache — ele estreita a detecção de roubo (§3a).
- **NUNCA** Argon2 com params default — sempre OWASP RFC 9106 §4 (t=3, m=64MiB, p=4).
- **NUNCA** `cookie path="/"` — sempre `/api/v1/auth/token`.
- **NUNCA** `SameSite=lax/none` — sempre `strict` (same-origin via NGINX).
- **NUNCA** `/refresh` em paralelo sem `withRefreshLock` — e **nunca** um segundo caller de refresh (bootstrap) fora do MESMO lock do interceptor (§11): rotação concorrente é lida como reuso e revoga a família.
- **NUNCA** guardar o refresh com `if (getAccessToken()) return true` — token expirado é truthy; o guard correto é o snapshot PRÉ-lock (§11).
- **NUNCA** montar o router antes do bootstrap resolver, nem esperar sessão dentro do `beforeLoad` (polling/`waitForAuthCheck` com deadline) — o deadline estourando vira redirect falso pro login (§10).
- **NUNCA** `fetch` cru em endpoint próprio autenticado — fora do `ApiClient` não há interceptor de 401 e o usuário fica preso até dar F5.
- **NUNCA** login que só limpa no `onSuccess` — access em memória e `queryClient` limpam ANTES da chamada (§12b).
- **NUNCA** cunhar sessão nova sem revogar a família do cookie anterior (§8b) — família órfã viva no Postgres é a dessincronia browser↔banco.
- **NUNCA** `persist` em Zustand auth store.
- **NUNCA** redirect manual no 401 — interceptor retenta com refresh primeiro.
- **NUNCA** refresh token em JSON body — backend strip defensivo + cookie só.
