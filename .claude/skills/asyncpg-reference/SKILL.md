---
name: asyncpg-reference
description: Repository pattern completo com asyncpg — método selection (fetch/fetchrow/fetchval/execute), contrato de input por operação (CREATE=Pydantic completo, UPDATE=ID+dict parcial+COALESCE, SELECT/DELETE=escalares tipados), SQL rules (parametrizado $1/$2 NUNCA f-string, RETURNING em writes, COALESCE para partial update, verbose INSERT/UPDATE sem dynamic SET clause), JSONB via orjson pool codec (pass dict/list direto, NUNCA orjson.loads/dumps manual), type mappings PG↔Python completos, bulk com ANY($1::type[]) e multi-row VALUES, singleton no fim do módulo, soft delete opt-in, serialization performance (orjson vs Pydantic 5x). INVOCAR ANTES de — escrever/editar qualquer `*_repository.py`, escolher fetch/fetchrow/fetchval/execute, montar INSERT/UPDATE/SELECT/DELETE, query com JSONB column, WHERE dinâmico em SELECT, partial UPDATE, bulk operation com lista de IDs, ou retornar dict/list[dict] de repo. NUNCA f-string em SQL (SQL injection); NUNCA dynamic SET clause em UPDATE (verbose explícito); NUNCA orjson.loads/dumps manual sobre coluna JSONB (codec já resolve); NUNCA repository retornando Pydantic (sempre dict/list[dict]/scalar — service que faz model_validate).
---

# asyncpg — Query Methods, Types & Patterns

Reference for writing asyncpg code against PostgreSQL: which query method to pick, how every PG type converts in both directions, common patterns for reads, writes and bulk operations, JSONB handling, and a benchmark-backed rule for serialization.

## Query Methods

| Method                      | Returns                       | Use when                       | Note                                                                                  |
| --------------------------- | ----------------------------- | ------------------------------ | ------------------------------------------------------------------------------------- |
| `conn.fetch(sql, *args)`    | `list[asyncpg.Record]`        | Multiple rows                  | Empty list if zero rows                                                               |
| `conn.fetchrow(sql, *args)` | `asyncpg.Record` or `None`    | Exactly one row                | Returns `None` if zero rows — check before `dict()`                                   |
| `conn.fetchval(sql, *args)` | single Python value or `None` | Single scalar                  | `None` ambiguous: zero rows OR SQL NULL. Add `COUNT(*)`/`EXISTS` if you need to disambiguate |
| `conn.execute(sql, *args)`  | `str` e.g. `'UPDATE 2'`       | Write without needing row back | Returns command tag; parse last token for affected-row count                          |

## Type Mappings (PostgreSQL ↔ Python)

| Tipo PostgreSQL                          | Tipo Python                                                                                            |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `anyarray`                               | `list`                                                                                                 |
| `anyenum`                                | `str`                                                                                                  |
| `anyrange`                               | `asyncpg.Range`, `tuple`                                                                               |
| `anymultirange`                          | `list[asyncpg.Range]`, `list[tuple]`                                                                   |
| `record`                                 | `asyncpg.Record`, `tuple`, `Mapping`                                                                   |
| `bit`, `varbit`                          | `asyncpg.BitString`                                                                                    |
| `bool`                                   | `bool`                                                                                                 |
| `box`                                    | `asyncpg.Box`                                                                                          |
| `bytea`                                  | `bytes`                                                                                                |
| `char`, `name`, `varchar`, `text`, `xml` | `str`                                                                                                  |
| `cidr`                                   | `ipaddress.IPv4Network`, `ipaddress.IPv6Network`                                                       |
| `inet`                                   | `ipaddress.IPv4Interface`, `ipaddress.IPv6Interface`, `ipaddress.IPv4Address`, `ipaddress.IPv6Address` |
| `macaddr`                                | `str`                                                                                                  |
| `circle`                                 | `asyncpg.Circle`                                                                                       |
| `date`                                   | `datetime.date`                                                                                        |
| `time`                                   | `offset-naïve datetime.time`                                                                           |
| `time with time zone`                    | `offset-aware datetime.time`                                                                           |
| `timestamp`                              | `offset-naïve datetime.datetime`                                                                       |
| `timestamp with time zone`               | `offset-aware datetime.datetime`                                                                       |
| `interval`                               | `datetime.timedelta`                                                                                   |
| `float`, `double precision`              | `float`                                                                                                |
| `smallint`, `integer`, `bigint`          | `int`                                                                                                  |
| `numeric`                                | `Decimal`                                                                                              |
| `json`, `jsonb`                          | `str` (default) — `dict`/`list` if pool has orjson codec registered                                    |
| `line`                                   | `asyncpg.Line`                                                                                         |
| `lseg`                                   | `asyncpg.LineSegment`                                                                                  |
| `money`                                  | `str`                                                                                                  |
| `path`                                   | `asyncpg.Path`                                                                                         |
| `point`                                  | `asyncpg.Point`                                                                                        |
| `polygon`                                | `asyncpg.Polygon`                                                                                      |
| `uuid`                                   | `uuid.UUID`                                                                                            |
| `tid`                                    | `tuple`                                                                                                |

The driver handles `datetime`, `uuid`, `Decimal`, `bytes` etc. natively — no manual serialization.

## JSONB with orjson codec

The pool registers a JSONB codec backed by orjson:

```python
await conn.set_type_codec(
    "jsonb",
    encoder=orjson.dumps,
    decoder=orjson.loads,
    schema="pg_catalog",
    format="binary",
)
```

With the codec active: pass `dict` / `list` directly on writes, receive `dict` / `list` directly on reads. No `json.dumps` / `json.loads` calls in repository code.

## Common Patterns

```python
# Multiple rows
rows = await conn.fetch("SELECT * FROM users WHERE org_id = $1", org_id)
results = [dict(row) for row in rows]

# Single row
row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
if row is None:
    return None
return dict(row)

# Scalar value
count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE org_id = $1", org_id)

# Write with RETURNING
row = await conn.fetchrow(
    "INSERT INTO users (name, email, org_id) VALUES ($1, $2, $3) RETURNING *",
    data.name, data.email, data.org_id,
)

# Execute (no return needed)
status = await conn.execute(
    "UPDATE users SET deleted_at = NOW() WHERE id = $1",
    user_id,
)
```

## Bulk Operations

### List parameter — `ANY($1::tipo[])`

```python
# SELECT by list of IDs
rows = await conn.fetch(
    "SELECT * FROM users WHERE id = ANY($1::bigint[])",
    user_ids,
)

# Bulk UPDATE
updated = await conn.fetch(
    """
    UPDATE users
    SET status = $1
    WHERE id = ANY($2::bigint[])
    RETURNING id, status
    """,
    "active",
    user_ids,
)

# Bulk DELETE
deleted = await conn.fetch(
    "DELETE FROM users WHERE id = ANY($1::bigint[]) RETURNING id, email",
    user_ids,
)
```

Always cast the array type explicitly (`::bigint[]`, `::text[]`, `::uuid[]`) — avoids inference surprises.

### Multi-row INSERT — `VALUES ($1,$2),($3,$4),...`

```python
inserted = await conn.fetch(
    """
    INSERT INTO users (email, first_name, last_name)
    VALUES
        ($1, $2, $3),
        ($4, $5, $6),
        ($7, $8, $9)
    RETURNING *
    """,
    email_1, first_1, last_1,
    email_2, first_2, last_2,
    email_3, first_3, last_3,
)
```

For larger batches (>10s of rows), prefer `conn.copy_records_to_table` or `executemany`.

## Performance: Serialization

Benchmark with `User` Pydantic model and one row of a wide `users` table (500k iterations, asyncpg pool, single Record):

| Approach                                              | µs/iter | Relative |
| ----------------------------------------------------- | ------- | -------- |
| `orjson.dumps(dict(row))`                             | 1.10    | 1.0×     |
| `User.model_validate(dict(row))` (no Mapping.register) | 2.87    | 2.6×     |
| `User.model_validate(row)` (with Mapping.register)    | 2.73    | 2.5×     |
| `orjson.dumps(User.model_validate(row).model_dump())` | 5.05    | 4.6×     |
| `User.model_validate(row).model_dump_json()`          | 5.22    | 4.7×     |

### Rule of thumb

- **Endpoints that read from DB and return as-is** → `orjson.dumps(dict(row))`. ~5× faster, no validation overhead the DB already enforces.
- **Endpoints that transform, compute, or accept user input** → Pydantic — the validation is the point.
- **`Mapping.register(asyncpg.Record)`** lets Pydantic accept `Record` directly without `dict(row)`. Marginal gain (~5%), not worth doing unless you have a hot path.

In FastAPI, returning `orjson.dumps(dict(row))` requires `Response(content=..., media_type="application/json")` or a custom `ORJSONResponse` — the default `JSONResponse` re-serializes.

## Repository Pattern — Contrato Rígido

asyncpg + orjson pool codec + Pydantic V2 já resolvem serialização. Repository só precisa escolher o método certo e respeitar o **tipo de input por operação**. Quem chama (route/service) faz `model_validate` no dict de volta.

### Input por operação

| Operação   | Input                                              | Por quê                                          |
| ---------- | -------------------------------------------------- | ------------------------------------------------ |
| **CREATE** | Pydantic model **completo**                        | Validação já rodou na borda; insert verbose 1:1 |
| **UPDATE** | `id` typed + `dict` com APENAS os campos a alterar | Caller omite o que não toca; COALESCE preserva  |
| **SELECT** | escalares tipados (`UUID`, `str`, `int`, `bool`)   | Sem Pydantic, sem dict — leitura é simples      |
| **DELETE** | escalares tipados                                  | Mesmo motivo                                     |

### Retorno

| Asyncpg call | Repository retorna                             | Quando                              |
| ------------ | ---------------------------------------------- | ----------------------------------- |
| `fetchval`   | valor puro (`int`, `UUID`, `bool`, `dict`...)  | 1 col 1 linha; RETURNING id; COUNT  |
| `fetchrow`   | `dict \| None`                                 | 1 linha completa                    |
| `fetch`      | `list[dict]` (vazio se nada)                   | N linhas                            |
| `execute`    | nada                                           | Write sem RETURNING                 |

**NUNCA** retorna Pydantic. **NUNCA** retorna `asyncpg.Record` cru. Sempre `dict` / `list[dict]` / scalar — service que faz `model_validate(dict)` se precisar de tipagem rica.

### CREATE — Pydantic completo + INSERT verbose

```python
# backend/src/api/models/user/user.py
class User(BaseModel):
    id: UUID
    email: EmailStr
    name: str
    organization_id: UUID
    metadata: dict = {}
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


# backend/src/api/repositories/user/user_repository.py
class UserRepository:
    def __init__(self):
        from config.database import get_pool
        self.pool = get_pool

    async def create(self, user: User) -> dict:
        async with self.pool().acquire() as conn:
            return dict(await conn.fetchrow(
                """
                INSERT INTO users (id, email, name, organization_id, metadata, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING *
                """,
                user.id, user.email, user.name, user.organization_id,
                user.metadata, user.created_at, user.updated_at,
            ))


# Singleton no fim do módulo
user_repository = UserRepository()
```

INSERT é verbose — TODAS as colunas listadas. Não use dynamic column list. Schema drift fica óbvio em PR.

### UPDATE — ID + dict parcial + COALESCE

```python
async def update(self, user_id: UUID, fields: dict) -> dict | None:
    """fields contém APENAS os campos que mudaram. Resto preserva (COALESCE)."""
    async with self.pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users
               SET email           = COALESCE($2, email),
                   name            = COALESCE($3, name),
                   organization_id = COALESCE($4, organization_id),
                   metadata        = COALESCE($5, metadata),
                   updated_at      = NOW()
             WHERE id = $1
               AND deleted_at IS NULL
             RETURNING *
            """,
            user_id,
            fields.get("email"),
            fields.get("name"),
            fields.get("organization_id"),
            fields.get("metadata"),
        )
        return dict(row) if row else None
```

Caller passa só o que mudou:

```python
# Em service / route
await user_repository.update(user_id, {"name": "New name"})
# email, organization_id, metadata ficam intactos
```

COALESCE em **TODAS** as colunas atualizáveis. `updated_at = NOW()` sem COALESCE (sempre atualiza).

**NUNCA** monte SET clause dinamicamente com if-else em Python:

```python
# BAD
sets = []
if fields.get("name"): sets.append("name = $X")
sql = f"UPDATE users SET {', '.join(sets)} WHERE id = $1"  # ❌
```

Verbose com COALESCE é estável, type-safe e o EXPLAIN não muda por request.

### SELECT — escalares tipados, WHERE dinâmico OK

```python
async def get_by_id(self, user_id: UUID) -> dict | None:
    async with self.pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1 AND deleted_at IS NULL",
            user_id,
        )
        return dict(row) if row else None

async def list_active(
    self,
    organization_id: UUID,
    q: str | None = None,
    role: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """WHERE dinâmico OK — valores SEMPRE $n."""
    sql = """
        SELECT * FROM users
         WHERE organization_id = $1
           AND deleted_at IS NULL
    """
    params: list = [organization_id]
    if q:
        params.append(f"%{q}%")
        sql += f" AND name ILIKE ${len(params)}"
    if role:
        params.append(role)
        sql += f" AND role = ${len(params)}"
    params.extend([limit, offset])
    sql += f" ORDER BY created_at DESC LIMIT ${len(params)-1} OFFSET ${len(params)}"

    async with self.pool().acquire() as conn:
        rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]
```

Critical:
- **NUNCA** Pydantic como input em SELECT. Escalares só.
- WHERE dinâmico OK — desde que `params.append(value)` + `$N` placeholder. **NUNCA** f-string com valor.
- Soft delete (`deleted_at IS NULL`) em todo SELECT da tabela que tem a coluna.

### DELETE — escalar + RETURNING para confirmação

```python
async def delete(self, user_id: UUID) -> bool:
    """Hard delete por padrão."""
    async with self.pool().acquire() as conn:
        deleted_id = await conn.fetchval(
            "DELETE FROM users WHERE id = $1 RETURNING id",
            user_id,
        )
        return deleted_id is not None


async def soft_delete(self, user_id: UUID) -> bool:
    """Soft delete — só onde tabela carrega deleted_at."""
    async with self.pool().acquire() as conn:
        deleted_id = await conn.fetchval(
            """
            UPDATE users
               SET deleted_at = NOW()
             WHERE id = $1 AND deleted_at IS NULL
             RETURNING id
            """,
            user_id,
        )
        return deleted_id is not None
```

`fetchval` + `RETURNING id` → `bool` claro (0 linhas → `None` → `False`).

Hard delete é o **default**. Soft delete é opt-in por tabela — se a tabela carrega `deleted_at`, todo SELECT filtra `deleted_at IS NULL`, e DELETE vira UPDATE.

## SQL Rules — resumo

1. **Sempre parametrizado** (`$1, $2…`). NUNCA f-string ou concat com valor.
2. **`RETURNING` em writes** — `fetchrow`/`fetchval` para data de volta; `execute()` quando não precisa.
3. **Verbose INSERT/UPDATE** — listar TODAS as colunas explícitas. NUNCA dynamic SET clause.
4. **Partial updates** — `COALESCE($n, column)` para callers omitirem sem resetar para NULL.
5. **Dynamic WHERE em SELECT** OK — valores SEMPRE como `$n`.
6. **Delete** — hard por padrão; soft (`deleted_at`) só onde a tabela tem a coluna.

## JSONB — orjson codec resolve

A pool registra codec orjson para JSONB:

```python
# config/database.py — bootstrap da pool
async def _init_conn(conn):
    await conn.set_type_codec(
        "jsonb",
        encoder=orjson.dumps,
        decoder=orjson.loads,
        schema="pg_catalog",
        format="binary",
    )

pool = await asyncpg.create_pool(dsn, init=_init_conn)
```

Com codec ativo:

```python
# Write: passa dict direto
await conn.execute(
    "INSERT INTO conversations (id, metadata) VALUES ($1, $2)",
    conv_id,
    {"channel": "whatsapp", "tags": ["urgent", "vip"]},   # ← dict direto
)

# Read: recebe dict direto
row = await conn.fetchrow("SELECT metadata FROM conversations WHERE id = $1", conv_id)
print(row["metadata"])  # → {"channel": "whatsapp", "tags": [...]}
```

**PROIBIDO**: `orjson.loads()` / `orjson.dumps()` manual sobre coluna JSONB. Codec faz o serviço em ambas direções.

## Singleton pattern

Todo repository expõe singleton no fim do módulo:

```python
# backend/src/api/repositories/user/user_repository.py
class UserRepository:
    def __init__(self):
        from config.database import get_pool
        self.pool = get_pool

    # ... métodos

user_repository = UserRepository()   # ← import-time singleton
```

Callsite:

```python
# backend/src/api/routes/users/list.py
from repositories.user.user_repository import user_repository

@router.get("/users")
async def list_users(auth: AuthDep):
    return await user_repository.list_active(auth.organization_id)
```

Sem DI framework, sem Container. Singleton é a "exceção controlada do projeto" (vide `code-quality.md`) — business logic NÃO usa singleton, mas data layer sim.

## Repository Don'ts

- **NUNCA** retornar Pydantic de repository — sempre `dict` / `list[dict]` / scalar.
- **NUNCA** f-string com valor em SQL.
- **NUNCA** dynamic SET clause em UPDATE — use COALESCE verbose.
- **NUNCA** `orjson.loads`/`dumps` manual em coluna JSONB.
- **NUNCA** Pydantic como input em SELECT/DELETE — escalares tipados.
- **NUNCA** esqueça `deleted_at IS NULL` em SELECT de tabela soft-deletable.
- **NUNCA** retorne `asyncpg.Record` cru — `dict(row)` no boundary.
- **NUNCA** instancie `UserRepository()` no callsite — use o singleton importado.
