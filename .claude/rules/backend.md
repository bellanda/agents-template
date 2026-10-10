---
paths:
  - "backend/**"
  - "**/*.py"
  - "config/app/**"
  - "config/docker/**"
  - "**/compose*.yaml"
---

# Backend — Python Stack & Invariants

> Cada linha sublinhada aponta a skill com a implementação completa. Invoque a skill ANTES de escrever código.

## Stack

| Layer         | Tool                                          | Skill / nota                                                                                                                                          |
| ------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Runtime       | **Python 3.13+**                              | Type hints públicos. `list[str]`, `X \| None`.                                                                                                        |
| Server        | **Granian** (prod) / uvicorn (dev `__main__`) | —                                                                                                                                                     |
| Pkg Manager   | **uv** only                                   | `uv add/run/sync`. NUNCA pip/poetry/conda.                                                                                                            |
| Framework     | **FastAPI** + Pydantic V2                     | DI estrita; Pydantic V2 valida input.                                                                                                                 |
| Serialization | **orjson**                                    | `CustomORJSONResponse` default.                                                                                                                       |
| DB Driver     | **asyncpg** + Raw SQL                         | Gate `database` (→ `asyncpg.md`) cobre repo contract, SQL, JSONB. asyncpg-only; único driver sync vive em `code/benchmarks/` (comparação sync×async). |
| DB Migrations | **dbmate**                                    | Gate `database` (→ `dbmate.md` + `schema-discipline.md`: PK/FK/CHECK/GIN/soft-delete).                                                                |
| Auth          | **PyJWT + Argon2-cffi**                       | Gate `auth` cobre tudo de `/auth/*` (→ `auth-hardened.md`). Login Google (popup auth-code) → `google-login.md`.                                       |
| HTTP Client   | **curl_cffi**                                 | Skill `http-client`. NUNCA requests/httpx.                                                                                                            |
| Data          | **Polars + DuckDB**                           | Padrão para data science / computação vetorial pesada. Pandas só quando realmente necessário.                                                         |
| Images        | **OpenCV Headless + AVIF**                    | Skill `image-processing`.                                                                                                                             |
| PDF           | **pikepdf + pypdfium2**                       | Skill `pdf-processing`. Stack padrão; só adiciona as deps se o app realmente processa PDF.                                                            |
| Fuzzy         | **RapidFuzz**                                 | —                                                                                                                                                     |
| Logging       | **structlog + stdlib + orjson**               | Ver `logs.md`. Setup: skill `logging-setup`.                                                                                                          |
| Cache + Msg   | **Valkey 8 (UDS) + NATS**                     | Gate `infra` (cache, messaging, decisão de arquitetura). Boundary: cache→Valkey, messaging→NATS.                                                      |
| Integrations  | **Meta (WhatsApp/FB/IG)**                     | Gate `integrations` (1 App/SaaS, 2 secrets `.env`, webhook HMAC, `facebook_user_id`). Só quando o projeto integra terceiros.                          |
| Config        | **YAML + Pydantic**                           | Skill `python-config-bootstrap`. `config/app/{env}.yaml` + `.env`.                                                                                    |
| Concurrency   | **anyio**                                     | Skill `anyio-concurrency`. NUNCA `asyncio.gather/create_task/wait_for/Lock/Queue` direto.                                                             |

## Invariantes não negociáveis

- **Config env-aware**: 3 yamls (`config/app/{local,staging,prod}.yaml`) + `.env` (secrets `SecretStr`) + `app.yaml` runtime. Settings com fail-fast no module load. Nova config/secret → invocar skill `python-config-bootstrap`.
- **Repository**: input por operação (CREATE=Pydantic completo, UPDATE=ID+dict parcial+COALESCE, SELECT/DELETE=escalares); retorno `dict`/`list[dict]`/scalar (NUNCA Pydantic); singleton no fim do módulo. SQL sempre `$1, $2` (NUNCA f-string) — **único carve-out**: interpolar (a) constante `Final` do próprio módulo (predicado `WHERE` compartilhado entre a query paginada e o `COUNT`) e (b) fragmento de `ORDER BY` vindo de whitelist fechado (`SortMap`). Nenhum dos dois carrega dado de request e todo VALOR continua em `$n` — não é injection. Gate `database`.
- **Listagem**: endpoint de coleção devolve SEMPRE `PagedResponse` (`items/total/skip/limit/has_more`) — NUNCA `list[...]` cru, NUNCA sem `LIMIT`, NUNCA `total=len(items)`. `has_more` exato pela **sentinela `LIMIT limit+1`** (fatia o extra, ecoa o `limit` pedido). `total` exato em **TODA página** (decisão 2026-10-09: página 7 aberta por link e o "48 de 1.355" do infinito precisam dele), via `COUNT(*)` separado, `sentinel(rows, params, total)` com `total` obrigatório, sem `wants_total`/lower-bound — **NUNCA `COUNT(*) OVER()`** (o `WindowAgg` varre o filtro inteiro por página, O(filtro) por request). `sort`/`order` do cliente é **só chave de dict** num `SortMap` fechado (chave desconhecida cai no default, nunca 422 — bookmark velho não branqueia a tela); só coluna `NOT NULL` entra no whitelist (elimina `NULLS LAST` e o 2º índice). **Todo `ORDER BY` termina com desempate por `id`** — `now()` é transaction-stable, então importação em lote gera `created_at` idênticos e o OFFSET duplica/pula linha. Índice composto `(escopo, chave_sort, id)` cobre as duas direções (scan reverso) — 3 chaves = 3 índices, não 6. Gate `database` (→ `list-pagination.md`).
- **Schema**: FK sempre indexada (leftmost); PK não recria; VARCHAR enum-like com CHECK; GIN só em JSONB containment; UNIQUE em soft-delete = partial `WHERE deleted_at IS NULL`. Gate `database`.
- **JSONB**: orjson pool codec resolve. Pass `dict`/`list` direto; NUNCA `orjson.loads/dumps` manual. Gate `database`.
- **Concurrency**: fan-out, timeout, file I/O em handler async, capacity limiter, memory stream, cancel shield → SEMPRE skill `anyio-concurrency`.
- **Cache + messaging**: TTL/contador/sliding window/invalidation (Valkey) e Pub/Sub/Queue/JetStream/KV (NATS) → gate `infra`. Valkey UDS only (`unix:///run/valkey/valkey.sock`), `decode_responses=False`, AOF everysec.
- **Auth**: qualquer toque em `/auth/*`, refresh_tokens repo, middleware auth, login/logout/refresh, password hashing, Google OAuth, cookie → gate `auth`. NUNCA decode JWT sem `options={"require": [...]}` + `issuer=` + `audience=`. NUNCA JWT no refresh (opaco + SHA-256). NUNCA Argon2 com defaults. Rotação = `claim_if_unused` atômico (nunca find+mark_used); cookie de refresh = clear-then-set; logout SEMPRE limpa cookies (nunca 401 antes); janela de graça de reuso (10–30s) recupera Set-Cookie perdido sem queimar a família + GC gatado no sucessor; **login revoga a família que veio no cookie ANTES de cunhar a nova** — best-effort (cookie ausente/inválido/de outro app = no-op silencioso, login NUNCA falha por causa da limpeza), senão a família anterior fica órfã viva no Postgres. Quando o endpoint de login não recebe o cookie (path-scopado em `/auth/token`, então `/auth/google` nunca o vê), a revogação é o handshake do cliente: `POST /auth/token/logout` e só então o login.
- **DateTime**: UTC only (`TIMESTAMPTZ`, `datetime.now(UTC)`). API responde ISO 8601 com sufixo `Z`. **Data montada em teste sai no MESMO fuso em que a query compara**: repositório de KPI/dashboard/aging converte (`AT TIME ZONE 'America/Sao_Paulo'`) antes de comparar `::date`, então setup com `CURRENT_DATE ± N` (fuso da sessão) ou `date.today()` (fuso do host) acerta ~21h por dia e erra nas 3h em que a data UTC já virou e a local não — falha reproduzível numa janela de horário, que some sozinha e parece regressão da mudança em curso.
- **Seed de bootstrap (`scripts/load_default_data.py`) é INSERT-ONLY por padrão**. Ele é upsert por chave: linha que já existe fica intacta, e o UPDATE coluna-a-coluna só sai com `--update` explícito — em base viva ele apaga o que a app gravou em runtime (`last_login_at`, CNPJ, `custom_roles`, `permissions_override`). O guard de ambiente (`ENVIRONMENT=prod|staging` exige `--yes-i-know`) vale **SÓ para `--update`**: o `CMD` do Dockerfile é `load_default_data.py online && exec granian`, então barrar o insert-only em prod não protege linha nenhuma e **derruba a API inteira pelo `&&`** — já aconteceu em produção. Os JSONs de `default_data/` carregam só identidade de bootstrap; coluna que a aplicação é dona em runtime NÃO entra no payload.

## Directory Layout (FastAPI)

```
backend/src/api/
  models/<dom>/<entity>.py              ← BaseModel 1:1 com tabela
  models/<dom>/<entity>_jsonb.py        ← JSONB shapes / enums / value objects
  repositories/<dom>/<entity>_repository.py
  repositories/shared/{listing,sorting}.py  ← sentinela LIMIT+1 + SortMap (ver Listagem)
  routes/<dom>/<file>.py                ← endpoints (<300 linhas ideal)
  routes/shared/list_params.py          ← ListParamsDep (skip/limit/search/sort/order)
  schemas/<dom>/<file>.py               ← DTOs request/response
```

- **Mirror**: `routes/X/Y.py` ↔ `schemas/X/Y.py` (mesmo subdir, mesmo nome).
- **Sufixos**: `_repository.py` (CRUD), `_jsonb.py` (sem tabela — sinaliza ao `check_schema.py` pular). NUNCA `_routes.py`/`_schemas.py`.
- **Inline schemas em route file = PROIBIDO**. Toda `BaseModel` request/response em `schemas/`.
- **Models**: 1 por arquivo. `class Model(BaseModel)` único. Schema do DB vive em `db/migrations/*.sql`; sync manual validado por `backend/scripts/check_schema.py` em `bash check.sh`.

## Code Style

- `async/await` para todo I/O — nunca bloqueie o event loop.
- User-facing strings em pt-BR.
- Princípios gerais (função-primeiro, sem `_private`, constantes UPPER_CASE no topo) → ver `cleancode.md`.

## Formatter (Ruff) — CRITICAL FOR EDIT TOOLS

Spaces only | 100 char line length | double quotes | LF line endings
