---
name: asyncpg-reference
description: asyncpg driver patterns — picking fetch/fetchrow/fetchval/execute, handling JSONB/UUID/datetime conversions, parameterized SQL with $1/$2, bulk operations with ANY($1::type[]), and serialization performance (orjson vs Pydantic). Use when writing or reviewing repository queries. Complements the repository contract in backend.md (rule) — rule defines INPUT shape per operation (CREATE=Pydantic, UPDATE=ID+dict+COALESCE, SELECT/DELETE=typed scalars), this skill covers how to express it in asyncpg.
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
