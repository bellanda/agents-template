# Backend — Python Stack & Invariants

> Cada linha sublinhada aponta a skill com a implementação completa. Invoque a skill ANTES de escrever código.

## Stack

| Layer         | Tool                                          | Skill / nota                                                                              |
| ------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Runtime       | **Python 3.13+**                              | Type hints públicos. `list[str]`, `X \| None`.                                            |
| Server        | **Granian** (prod) / uvicorn (dev `__main__`) | —                                                                                         |
| Pkg Manager   | **uv** only                                   | `uv add/run/sync`. NUNCA pip/poetry/conda.                                                |
| Framework     | **FastAPI** + Pydantic V2                     | DI estrita; Pydantic V2 valida input.                                                     |
| Serialization | **orjson**                                    | `CustomORJSONResponse` default.                                                           |
| DB Driver     | **asyncpg** + Raw SQL                         | Skill `asyncpg-reference` cobre repo contract, SQL, JSONB.                                |
| DB Migrations | **dbmate**                                    | Skill `dbmate` + skill `db-schema-discipline` (PK/FK/CHECK/GIN/soft-delete).              |
| Auth          | **PyJWT + Argon2-cffi**                       | Skill `auth-hardened` cobre tudo de `/auth/*`.                                            |
| HTTP Client   | **curl_cffi**                                 | Skill `http-client`. NUNCA requests/httpx.                                                |
| Data          | **Polars**                                    | Pandas é PROIBIDO.                                                                        |
| Images        | **OpenCV Headless + AVIF**                    | Skill `image-processing`.                                                                 |
| PDF           | **pikepdf + pypdfium2**                       | Skill `pdf-processing`.                                                                   |
| Fuzzy         | **RapidFuzz**                                 | —                                                                                         |
| Logging       | **structlog + stdlib + orjson**               | Ver `logging.md`. Setup: skill `logging-setup`.                                           |
| Cache         | **Valkey 8 (UDS)**                            | Skill `valkey-cache`. Boundary: cache→Valkey, messaging→NATS.                             |
| Config        | **YAML + Pydantic**                           | Skill `python-config-bootstrap`. `config/app/{env}.yaml` + `.env`.                        |
| Concurrency   | **anyio**                                     | Skill `anyio-concurrency`. NUNCA `asyncio.gather/create_task/wait_for/Lock/Queue` direto. |

## Invariantes não negociáveis

- **Config env-aware**: 3 yamls (`config/app/{local,staging,prod}.yaml`) + `.env` (secrets `SecretStr`) + `app.yaml` runtime. Settings com fail-fast no module load. Nova config/secret → invocar skill `python-config-bootstrap`.
- **Repository**: input por operação (CREATE=Pydantic completo, UPDATE=ID+dict parcial+COALESCE, SELECT/DELETE=escalares); retorno `dict`/`list[dict]`/scalar (NUNCA Pydantic); singleton no fim do módulo. SQL sempre `$1, $2` (NUNCA f-string). Skill `asyncpg-reference`.
- **Schema**: FK sempre indexada (leftmost); PK não recria; VARCHAR enum-like com CHECK; GIN só em JSONB containment; UNIQUE em soft-delete = partial `WHERE deleted_at IS NULL`. Skill `db-schema-discipline`.
- **JSONB**: orjson pool codec resolve. Pass `dict`/`list` direto; NUNCA `orjson.loads/dumps` manual. Skill `asyncpg-reference`.
- **Concurrency**: fan-out, timeout, file I/O em handler async, capacity limiter, memory stream, cancel shield → SEMPRE skill `anyio-concurrency`.
- **Cache**: TTL/contador/sliding window/invalidation → skill `valkey-cache`. UDS only (`unix:///run/valkey/valkey.sock`), `decode_responses=False`, AOF everysec.
- **Auth**: qualquer toque em `/auth/*`, refresh_tokens repo, middleware auth, login/logout/refresh, password hashing, Google OAuth, cookie → skill `auth-hardened`. NUNCA decode JWT sem `options={"require": [...]}` + `issuer=` + `audience=`. NUNCA JWT no refresh (opaco + SHA-256). NUNCA Argon2 com defaults.
- **DateTime**: UTC only (`TIMESTAMPTZ`, `datetime.now(UTC)`). API responde ISO 8601 com sufixo `Z`.

## Directory Layout (FastAPI)

```
backend/src/api/
  models/<dom>/<entity>.py              ← BaseModel 1:1 com tabela
  models/<dom>/<entity>_jsonb.py        ← JSONB shapes / enums / value objects
  repositories/<dom>/<entity>_repository.py
  routes/<dom>/<file>.py                ← endpoints (<300 linhas ideal)
  schemas/<dom>/<file>.py               ← DTOs request/response
```

- **Mirror**: `routes/X/Y.py` ↔ `schemas/X/Y.py` (mesmo subdir, mesmo nome).
- **Sufixos**: `_repository.py` (CRUD), `_jsonb.py` (sem tabela — sinaliza ao `check_schema.py` pular). NUNCA `_routes.py`/`_schemas.py`.
- **Inline schemas em route file = PROIBIDO**. Toda `BaseModel` request/response em `schemas/`.
- **Models**: 1 por arquivo. `class Model(BaseModel)` único. Schema do DB vive em `db/migrations/*.sql`; sync manual validado por `backend/scripts/check_schema.py` em `bash check.sh`.

## Code Style

- `async/await` para todo I/O — nunca bloqueie o event loop.
- User-facing strings em pt-BR.
- **Sem `_private` em Python.** Classes expõem direto. Internos = funções de módulo não exportadas.
- **Constantes UPPER_CASE no topo do arquivo** > atributos ocultos.
- **Função-primeiro.** Classe só com estado real (pool, client, cache singleton). Ver `code-quality.md`.

## Formatter (Ruff) — CRITICAL FOR EDIT TOOLS

Spaces only | 100 char line length | double quotes | LF line endings
