# Python — Core Stack & Patterns

## Stack

| Layer         | Tool                            | Rule                                                                                                      |
| ------------- | ------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Runtime       | **Python 3.13+**                | Type hints em toda função pública. Sintaxe moderna: `list[str]`, `X \| None`                              |
| Server        | **Granian** (Rust ASGI)         | Docker/prod: 100% Granian. Dev `__main__`: uvicorn (better debug output)                                  |
| Pkg Manager   | **uv** only                     | `uv add`, `uv run`, `uv sync`. NEVER pip/poetry/conda                                                     |
| Framework     | **FastAPI**                     | Strict dependency injection, Pydantic V2 para input validation                                            |
| Serialization | **orjson**                      | Mandatório para todo JSON. `CustomORJSONResponse` como default response class                             |
| DB Driver     | **asyncpg** + Raw SQL           | Runtime CRUD. SQL parametrizado (`$1, $2…`), NEVER string concat                                          |
| DB Migrations | **dbmate**                      | Plain `.sql` em `db/migrations/`. Tracked via `schema_migrations`                                         |
| DB Strategy   | **Relacional + JSONB**          | JSONB estratégico com B-Tree/GIN indexes. Validado por Pydantic V2                                        |
| Auth          | **PyJWT + Argon2-cffi**         | JWT stateless sessions, Argon2 password hashing                                                           |
| HTTP Client   | **curl_cffi**                   | Substitui requests/httpx. HTTP/3, TLS fingerprinting, libcurl performance                                 |
| Data          | **Polars**                      | Tudo tabular/data. Pandas é PROIBIDO                                                                      |
| Images        | **OpenCV Headless + AVIF**      | Processa qualquer input, sempre output AVIF                                                               |
| PDF           | **pikepdf + pypdfium2**         | Estrutura (pikepdf) + rendering/extraction (pypdfium2)                                                    |
| Fuzzy Match   | **RapidFuzz**                   | Text deduplication, fuzzy filtering                                                                       |
| Logging       | **structlog + stdlib + orjson** | NDJSON em prod, ConsoleRenderer em dev, QueueHandler async-safe. Ver `logging.md`                         |
| Cache         | **Valkey 8 (UDS)**              | `valkey-py` async via `unix:///run/valkey/valkey.sock`. AOF everysec. Ver `## Cache (Valkey)`             |
| Config        | **YAML + Pydantic**             | `config/app/{local,staging,prod}.yaml` (versionado) + `.env` (secrets). Ver `## Environment & Config` |

## Environment & Config

| Categoria        | Onde vive                                         | Versionado | Lido por                                               |
| ---------------- | ------------------------------------------------- | ---------- | ------------------------------------------------------ |
| Secrets          | `.env` (root)                                     | Não        | `getenv_or_raise_exception` em `config/tools.py`       |
| Config app       | `config/app/{local,staging,prod}.yaml`        | Sim        | `Settings` (Pydantic + PyYAML) em `config/settings.py` |
| Runtime local    | `app.yaml` (root, copy do pai)                    | Não        | `Settings()` no module load (fail-fast)                |
| Docker overrides | `config/docker/compose.{local,staging,prod}.yaml` | Sim        | `cp` para `compose.override.yaml`                      |

Bootstrap por ambiente:

```bash
cp config/app/local.yaml app.yaml
cp config/docker/compose.local.yaml compose.override.yaml
# .env: provisionado manualmente (cofre / 1Password / scp)
```

Regras:

- **Nova config (env-aware)?** Edita os **3** `config/app/{env}.yaml` (mesmo que valor seja igual entre 2). Adiciona o sub-model em `Settings` em `config/settings.py`.
- **Nova secret?** Adiciona em `.env.example` (vazia) + field `SecretStr` em `Settings`. Instrua o usuário a popular `.env` local manualmente. **NUNCA** commit valor real.
- **`config/api.py`, `config/database.py` etc são shims.** Lêem de `settings.*` e expõem atributos `UPPER_CASE` por compatibilidade com callsites existentes — não introduza lógica nova ali.
- **Fail-fast garantido**: `settings = _load()` roda no import; sem `app.yaml` ou secret obrigatória, app explode no startup.
- **`compose.yaml` base**: `${VAR}` substitution permitido APENAS para secrets vindas do `.env` (ex: `${POSTGRES_PASSWORD}`). Configs por env (POSTGRES*DB, VITE*\*, GRANIAN_WORKERS_MAX_RSS) ficam **literais** em `compose.{env}.yaml > environment:`.
- **Granian runtime**: `GRANIAN_*` env vars consumidas pelo Dockerfile CMD via shell. Constantes ficam no `compose.yaml` base; o que varia por env (`GRANIAN_WORKERS_MAX_RSS`) vai no override.
- **Secondary Python processes** (cron-worker etc): se compartilham o mesmo deploy, montam o mesmo `app.yaml` via volume e têm seu próprio `settings.py` mínimo (sem pydantic se justificar leveza).

## Directory Layout

```
backend/src/api/
  models/<dominio>/<entidade>.py             ← BaseModel = espelho 1:1 de uma tabela
  models/<dominio>/<entidade>_jsonb.py       ← value objects / shapes JSONB / enums
  repositories/<dominio>/<entidade>_repository.py  ← CRUD asyncpg (sufixo `_repository.py`)
  routes/<dominio>/<arquivo>.py              ← endpoints (<300 linhas ideal)
  schemas/<dominio>/<arquivo>.py             ← request/response DTOs
```

**Regra do mirror:** `routes/X/Y.py` ↔ `schemas/X/Y.py`. Mesmo subdiretório, mesmo nome de arquivo. Schema vive ao lado do contrato HTTP, **não** ao lado da tabela.

**Sufixos:**

- `_repository.py` em `repositories/`.
- `_jsonb.py` em `models/` (sinaliza ao `check_schema.py` para pular).
- **NÃO** usar `_routes.py` ou `_schemas.py` — diretório já desambigua.

**`_jsonb.py`:** todo BaseModel SEM tabela (shape JSONB, value object, enum, payload de cache) vai aqui. O entity file só tem o BaseModel que espelha a tabela; pode importar de `_jsonb.py` para tipar campos JSONB.

**Inline schemas em route files: PROIBIDO.** Toda `BaseModel` de request/response vai para `schemas/<dominio>/<mesmo-nome-da-rota>.py`.

**`__sql_table__` override** (raríssimo): APENAS quando tabela tem nome legado divergente do model e renomear não é viável. NÃO use `__sql_table__ = None` — se não é tabela, vai pra `_jsonb.py`.

## Models — Pydantic only

One file per entity. Single definition por arquivo: `class Model(BaseModel)`.

- Input validation em writes (request bodies, repository CREATE).
- Typed access em services (após `model_validate(dict_from_repo)`).

Schema do DB vive em `db/migrations/*.sql` (dbmate). Pydantic models ficam em sync com SQL **manualmente** — `backend/scripts/check_schema.py` valida 1:1 em `bash check.sh`.

**Schema Drift:** sem autogenerate. Naming convention: `User` ↔ `users` ↔ `*_users_*.sql`. PR template tem checklist obrigatório (mudou schema? atualizou Pydantic? atualizou repository?).

## Repository Pattern — Contrato Rígido

asyncpg + orjson codec na pool + Pydantic V2 já resolvem serialização. O repo só precisa escolher o método certo e respeitar o tipo de input. Quem chama (route/service) faz `model_validate`.

### Métodos asyncpg → retorno

| Método                   | Retorno                                                | Quando usar                                      |
| ------------------------ | ------------------------------------------------------ | ------------------------------------------------ |
| `fetchval(sql, *params)` | valor puro (`int`, `UUID`, `bool`, `dict` se JSONB...) | 1 coluna, 1 linha. `RETURNING id`, COUNT, EXISTS |
| `fetchrow(sql, *params)` | `dict \| None`                                         | 1 linha completa                                 |
| `fetch(sql, *params)`    | `list[dict]` (vazio se nada)                           | N linhas                                         |
| `execute(sql, *params)`  | nada (status string descartável)                       | INSERT/UPDATE/DELETE sem `RETURNING`             |

Codec orjson na pool + Pydantic V2 cobrem JSONB ↔ dict em ambas direções. **Não** `orjson.loads`/`dumps` manual sobre dados de DB.

### Entrada — por tipo de operação

1. **CREATE** — recebe **Pydantic model completo**. INSERT verbose com todas as colunas. `RETURNING *` → `dict`.
2. **UPDATE** — recebe **ID (typed)** + **dict APENAS com os campos a alterar** (não precisa mandar todos). SET com `COALESCE($n, column)` em TODAS as colunas atualizáveis: caller passa `None` para o que não toca, COALESCE preserva o valor atual. `RETURNING *` → `dict | None`.
3. **SELECT** — recebe **só parâmetros escalares tipados** (`UUID`, `str`, `int`, `bool`). NUNCA Pydantic, NUNCA dict. WHERE dinâmico ok desde que valores fiquem como `$n`.
4. **DELETE** — recebe **só parâmetros escalares tipados**. Hard delete por padrão (`DELETE FROM`); soft delete (`SET deleted_at = NOW()`) só onde a tabela carrega a coluna. `RETURNING id` via `fetchval` → `bool`.

### Outras regras

- Repos retornam `dict` / `list[dict]` / scalar. NUNCA Pydantic.
- Singleton no fim do arquivo (`user_repository = UserRepository()`).
- Layer: `route → repository` ou `route → service → repository`.
- Soft delete é **opt-in por tabela**: onde a coluna `deleted_at` existe, filtrar `deleted_at IS NULL` em todo SELECT. Default é hard delete + FK `CASCADE`/`SET NULL`.

## SQL Rules

1. Sempre parametrizado (`$1, $2…`). NEVER f-string/concat values.
2. `RETURNING` em writes — `fetchrow`/`fetch` para data back, `execute()` quando não precisa.
3. Delete — hard delete por padrão; soft delete (`deleted_at`) só onde a tabela tem a coluna, e aí todo SELECT filtra `deleted_at IS NULL`.
4. Verbose INSERT/UPDATE — listar todas as colunas explícitas. NEVER dynamic SET clause.
5. Partial updates — `COALESCE($n, column)` para callers omitirem sem resetar para NULL.
6. Dynamic WHERE em SELECTs ok, valores como `$n`.

## Schema & Index Discipline

Vale para toda migration em `db/migrations/*.sql`.

- **Índice de PK é automático.** NUNCA `CREATE INDEX` sobre a coluna PK — o `PRIMARY KEY` já cria índice único. Índice redundante só gera write amplification.
- **Toda FK tem índice.** Postgres não indexa FK sozinho; sem índice, `DELETE`/`UPDATE` no pai vira seq scan no filho. A coluna FK precisa ser **leftmost** de algum índice — se já é leftmost de um composto, ok; senão, índice dedicado `ix_<tabela>_<coluna>`.
- **CHECK em coluna enum-like.** Toda `VARCHAR` que espelha um `StrEnum`/`frozenset`/conjunto fechado de constantes no código ganha `CONSTRAINT ck_<tabela>_<coluna> CHECK (col IN (...))`. Os valores espelham o enum do código — mantêm sync junto com o Pydantic.
- **GIN só em JSONB consultado por conteúdo** (`@>`, `?`, `?|`, `?&`). Extração (`->>`, `#>>`) e unnesting (`jsonb_array_elements`) NÃO se beneficiam de GIN — para esses, índice de expressão B-Tree na chave específica, e só quando o WHERE for quente.
- **Soft delete** (tabela com `deleted_at`): todo `UNIQUE` vira **partial unique index** `WHERE deleted_at IS NULL` — senão linha morta bloqueia recadastro.
- **Naming:** `ix_` índice comum, `ux_`/`uq_` unique (índice/constraint), `ck_` check. Distintivo e greppável.

## JSONB

asyncpg auto-converte via orjson pool codec. Pass `dict`/`list` direto em writes, recebe `dict`/`list` em reads. **PROIBIDO:** `orjson.loads()` / `orjson.dumps()` manual sobre dados de DB.

## DateTime — Backend

- Storage e transmissão **UTC only**. `TIMESTAMPTZ`, `datetime.now(UTC)`.
- API sempre retorna ISO 8601 com sufixo `Z` (`"2026-03-26T15:30:00Z"`). Nunca offset local, nunca naive string.

## Concurrency — Invariantes

Default = **anyio** (structured concurrency). Trabalho concorrente vive sempre dentro de um escopo (`async with anyio.create_task_group():`). Implementação completa (task groups, timeouts, capacity limiters, memory streams, cancel shielding, ExceptionGroup) na **skill `anyio-concurrency`** — invocar ao escrever fan-out, timeout, queue entre tasks, ou cleanup crítico.

- **Fan-out**: `anyio.create_task_group()` + `tg.start_soon`. NUNCA `asyncio.gather`/`create_task` solto.
- **Timeout**: `anyio.fail_after` / `move_on_after`. NUNCA `asyncio.wait_for`.
- **Sync bloqueante** (Polars, OpenCV, pikepdf, RapidFuzz): `await anyio.to_thread.run_sync(fn, *args)`. Nunca direto no loop.
- **File I/O / subprocess**: `anyio.Path(p).read_text()` / `anyio.run_process([...])`. Nunca `open()` / `subprocess.run` em handler async.
- **Lock/Queue**: versões `anyio.*`. NUNCA `asyncio.Lock`/`Queue` (não respeitam CancelScope).
- **`CancelledError`** = "pare e libere recursos" — nunca engulir com `except Exception: pass`. Cleanup em `finally`; sobreviver a cancelamento externo via `anyio.CancelScope(shield=True)`.
- **Background fora do request**: NATS / Celery / queue persistente. NUNCA `asyncio.create_task` em handler — task órfã sem cleanup.

## Cache (Valkey)

Stack: `valkey-py 6+` async client, **UDS only** (`unix:///run/valkey/valkey.sock`), AOF everysec, `decode_responses=False` (mantém bytes + orjson). Boundary firme: **cache → Valkey, messaging → NATS**. Não duplica responsabilidades.

| Necessidade                            | Use     | Motivo                                 |
| -------------------------------------- | ------- | -------------------------------------- |
| Cache TTL, contadores, sliding windows | Valkey  | Hot path, latência ~50-80μs            |
| Pub/Sub, Queue Groups, JetStream       | NATS    | Messaging persistente, fan-out durável |
| KV cross-cluster                       | NATS KV | Não é nosso caso atual                 |

Convenção de chave: `cache:<dominio>:<entidade>:<id>`. TTLs padrão: 60s auth, 300s org config, 3600s listas read-heavy. **Banido em hot path:** `KEYS *` (use `SCAN`), LUA bloqueante em loop async, `decode_responses=True`.

Para patterns aprofundados (cache-aside, pipeline batch, sliding window LUA, invalidação event-driven via NATS): **invocar skill `valkey-cache`**.

## Auth — Invariantes

Stack canônico cross-projeto. Implementação completa (encode/decode, rotation flow, código frontend) na **skill `auth-hardened`** — invocar antes de tocar `/auth/*`, repository de refresh, middleware de auth, password hashing, OAuth handler ou cookie config.

- **Access token (JWT curto)**: HS256 com claims `sub`, `fam` (UUID da family de refresh), `jti`, `iss`, `aud`, `exp`, `iat`. Decode SEMPRE com `options={"require": [...]}` + `issuer=` + `audience=`. TTL ~15min, memória only.
- **Refresh token (opaco)**: `secrets.token_urlsafe(64)`, armazenado como SHA-256 hex em `refresh_tokens(token_hash CHAR(64))`. Tabela carrega `family UUID`, `used BOOLEAN`, `revoked_at`, `expires_at`. **Rotation = family + used**: reuso de token usado → revoga family inteira + `deny_family(family)` no Valkey.
- **JTI denylist**: key `denylist:family:{fam}` em Valkey, TTL = TTL do access. Logout revoga family + deny. Middleware checa `EXISTS` após decode.
- **Argon2id**: OWASP RFC 9106 §4 — `time_cost=3, memory_cost=64*1024, parallelism=4`. Login usa `verify_and_update` para rehash. `ARGON2_FAST=1` em test env.
- **Google OAuth**: `google.oauth2.id_token.verify_oauth2_token(id_token, Request(), audience=...)`. NUNCA `/userinfo`. Frontend entrega `credential` (id_token); backend verifica + cria session.
- **Cookie refresh**: `httponly=True, samesite="strict", path="/api/v1/auth/token"`, `secure` per env. Path scopado tira cookie de 99% dos requests.
- **Config**: `jwt.{issuer,audience,algorithm,access_token_expire_minutes,refresh_token_expire_days,leeway_seconds}` + `cookies.secure` em `config/app/{env}.yaml`. Secrets `JWT_SECRET_KEY`, `VALKEY_PASSWORD`, `GOOGLE_OAUTH_CLIENT_SECRET` em `.env`.

### Don'ts

- **NUNCA** JWT no refresh — opaco only.
- **NUNCA** plain text de refresh no DB — só SHA-256.
- **NUNCA** persistir access em browser storage (ver `frontend.md > Auth`).
- **NUNCA** decode JWT sem `options={"require": [...]}` + `issuer=` + `audience=` + `algorithms=[settings.jwt.algorithm]`.
- **NUNCA** Google OAuth via `/userinfo` — sempre `id_token.verify_oauth2_token`.
- **NUNCA** logout que só apaga cookie sem revogar family + denylist no Valkey.
- **NUNCA** Argon2 com params default da lib — sempre OWASP explícitos.

## Code Style

- `async/await` para todo I/O — nunca bloqueie o event loop.
- User-facing strings em pt-BR. Repository/service singletons no fim do módulo.
- **Sem `_private` em Python.** Classes expõem direto (`self.pool`, não `self._pool`). Internos = funções de módulo não exportadas.
- **Constantes explícitas > atributos ocultos.** Thresholds, timeouts, limits, chunk sizes como `UPPER_CASE` no topo do arquivo.
- **Função-primeiro.** Default = função de módulo. Classe só com estado real (pool, client, cache singleton). Ver `code-quality.md`.

## Formatter (Ruff) — CRITICAL FOR EDIT TOOLS

Spaces only | 100 char line length | double quotes | LF line endings
