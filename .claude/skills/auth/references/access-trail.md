# Trilha de acesso (`user_access_events`)

> Padrão de 2026-10-14 (nasceu no Dossiê do atleta da Nexarena, prova de aceite em processo
> judicial). Vale para TODO app com login. Registro de acesso a aplicação: Marco Civil da Internet,
> art. 15, exige guardar ≥ 6 meses (data/hora + IP).

## O que é um "acesso"

| kind | Quando grava | Custo |
|---|---|---|
| `LOGIN` | login explícito bem-sucedido (Google, senha) | 1 INSERT por login |
| `SESSION_RESUMED` | refresh-token rotation que **inicia** uma sessão nova da mesma família (aparelho) | 1 chamada Valkey por refresh; INSERT só na 1ª da janela |

**Nunca** por uso de access token (cada request autenticada viraria uma linha). O gancho é a
rotação do refresh: o access vive em memória (30 min), então todo abrir/recarregar do app e a cada
~30 min de uso já passa por `POST /auth/token` (refresh), que já escreve no Postgres.

## Throttle (Valkey, uma ida, janela deslizante)

```python
ACCESS_TRAIL_WINDOW_SECONDS: Final = 2 * 60 * 60  # > TTL do access (30 min): uso contínuo = 1 linha

previous = await valkey.set(f"access_trail:{family}", b"1", ex=ACCESS_TRAIL_WINDOW_SECONDS, get=True)
if previous is None:  # a chave não existia: sessão nova nesta família
    await user_access_event_repository.create(conn, kind="SESSION_RESUMED", ...)
```

- `SET … EX … GET` desliza a janela a cada refresh e diz se a sessão é nova, atômico.
- Família = `refresh_tokens.family` (um aparelho/navegador). Ficou 2 h sem usar e voltou → linha nova.
- Login grava `LOGIN` e **semeia** a chave da família nova (mesmo `SET`), senão o refresh logo
  depois do login duplica como `SESSION_RESUMED`.
- Valkey fora do ar → **não grava** (`log.warning`), nunca cai para INSERT incondicional.

## Tabela

```sql
CREATE TABLE user_access_events (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind        VARCHAR(16) NOT NULL,
    method      VARCHAR(16),          -- só em LOGIN
    family      UUID,                 -- refresh_tokens.family (sessão/aparelho)
    ip_address  INET,
    user_agent  VARCHAR(400),
    CONSTRAINT ck_user_access_events_kind CHECK (kind IN ('LOGIN', 'SESSION_RESUMED')),
    CONSTRAINT ck_user_access_events_method CHECK (method IN ('google', 'password')),
    CONSTRAINT ck_user_access_events_kind_method CHECK ((kind = 'LOGIN') = (method IS NOT NULL))
);
CREATE INDEX ix_user_access_events_user_occurred ON user_access_events (user_id, occurred_at DESC, id DESC);
```

Append-only. Sem expurgo por ora (volume ~2–4 linhas/dia por usuário ativo); decisão revisitável —
expurgo, se vier, nunca abaixo de 6 meses. IP e UA são dado pessoal guardado de propósito (prova).

## Código (mesma forma em todo app)

- `core/request_evidence.py`: `request_evidence(request) -> (ip | None, user_agent[:400] | None)`,
  IP real via `client_ip_from_scope` do logging middleware (X-Real-IP do nginx/Cloudflare).
- `repositories/auth/user_access_event_repository.py`: `create(...)`, `list_by_user(conn, user_id, *, limit)`.
- `services/auth/access_trail.py`: `record_login(conn, request, *, user_id, family, method)` e
  `record_session_resumed(conn, request, *, user_id, family)`. **Best-effort**: try/except +
  `log.exception("access_trail_record_failed", ...)`; nunca derruba login nem refresh.
- Ganchos:
  - toda rota de login (Google `/auth/google`, senha `grant_type=password`, variantes do app);
  - rota de refresh: `refresh_access_token` devolve `user_id` + `family` da linha reivindicada
    (cobre também a janela de graça, que passa por `_issue_rotated_pair`); a rota tira esses campos
    do corpo antes de responder.
- `get_conn` sem transação aberta: falha no INSERT não envenena a conexão do login.

## Don'ts

- NUNCA gravar por request autenticada / por uso do access token.
- NUNCA polling/consulta no Postgres para decidir "sessão nova" — o estado é do Valkey.
- NUNCA bloquear login/refresh por falha na trilha.
- NUNCA tratar refresh como `LOGIN`: são fatos diferentes no relatório.
