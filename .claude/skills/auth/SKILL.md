---
name: auth
description: PORTÃO obrigatório de autenticação (cross-projeto). INVOCAR ANTES de escrever/alterar QUALQUER coisa de auth — endpoint `/auth/*`, login/logout/refresh flow, repository de refresh_tokens, middleware de auth, configuração de cookie, password hashing (Argon2id), claims JWT (iss/aud/fam/jti), JTI denylist, e Login com Google (popup `@react-oauth/google` auth-code, `GoogleSignInButton`, `google_oauth_service`, rota `/auth/google`, exchange do code, verify id_token via JWKS). Checklist de invariantes + roteia pras references profundas. NUNCA persistir access token em localStorage/sessionStorage/Zustand persist (vai pra memória); refresh SEMPRE em cookie HttpOnly path-scopado SameSite=Strict; NUNCA aceitar id_token do front sem re-verificar no backend; NUNCA cadastrar redirect URI no Console p/ popup; NUNCA retornar refresh token no JSON. Complementa as seções `## Auth` em `backend.md` e `frontend.md` (rules = invariantes; aqui = implementação).
---

# Auth — O Portão

Ponto de entrada único de autenticação. **NUNCA toque em auth sem passar por aqui.** Os invariantes
vivem nas seções `## Auth` de `backend.md` e `frontend.md` (rules, sempre on); a implementação
profunda está nas references abaixo.

## Checklist (em ordem; desça o que a tarefa exige)

- [ ] **1. Core de sessão** — endpoint `/auth/*`, login/logout/refresh, repo `refresh_tokens`,
  middleware, cookie, claims JWT, Argon2id, family rotation, JTI denylist em Valkey →
  **`references/auth-hardened.md`**.
- [ ] **2. Login com Google** — botão/popup `@react-oauth/google` (auth-code), `google_oauth_service`,
  rota `/auth/google`, exchange do code, verify id_token via JWKS, get-or-create user →
  **`references/google-login.md`** (reusa o core de `auth-hardened.md`).

## Invariantes não negociáveis (sempre)

- Access token em **memória** — **NUNCA** localStorage/sessionStorage/Zustand persist.
- Refresh em **cookie HttpOnly** path-scopado SameSite=Strict — **NUNCA** no corpo JSON.
- Refresh on 401 concurrency-safe (Web Locks API + BroadcastChannel).
- Senha: **Argon2id** (OWASP RFC 9106 §4). JWT com claims `iss/aud/fam/jti`; refresh opaco family+used+SHA-256.
- Google: **sempre** re-verificar id_token no backend (JWKS, `id_token.verify_oauth2_token`), nunca
  via `/oauth2/v3/userinfo`; popup usa só Authorized JavaScript origins (sem redirect URIs).

## References

- `references/auth-hardened.md` — core completo (JWT, refresh family, cookie, Argon2, denylist, frontend refresh lock).
- `references/google-login.md` — Login com Google (popup auth-code, exchange, verify, setup Console + yaml/.env).
