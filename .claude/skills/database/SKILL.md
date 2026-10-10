---
name: database
description: PORTÃO obrigatório de banco de dados (Postgres + asyncpg + dbmate). INVOCAR ANTES de QUALQUER trabalho de DB — escrever/editar `*_repository.py` (fetch/fetchrow/fetchval/execute, INSERT/UPDATE/SELECT/DELETE, COALESCE partial update, WHERE dinâmico, bulk com ANY($1::type[]), JSONB via orjson codec, retorno dict/list[dict]/scalar), escrever migration `.sql` em `db/migrations/` (CREATE TABLE/INDEX, FK, CHECK em VARCHAR enum-like, GIN em JSONB, partial UNIQUE com soft-delete, naming ix_/ux_/uq_/ck_), operar dbmate (new/up/down/rollback, schema dump, squash, Docker/CI), ou escrever/alterar endpoint de LISTAGEM paginada (PagedResponse, sentinela LIMIT+1, has_more, total, ORDER BY com whitelist e desempate, scroll infinito/páginas numeradas, índice composto por chave de ordenação). Checklist ordenado de invariantes + roteia pras references profundas. NUNCA f-string em SQL (injection, com carve-out único para constante Final + whitelist de ORDER BY); NUNCA COUNT(*) OVER() em lista; NUNCA ORDER BY sem desempate por coluna única; NUNCA dynamic SET clause em UPDATE; NUNCA orjson.loads/dumps manual sobre JSONB; NUNCA repository retornando Pydantic; NUNCA índice em coluna PK; NUNCA UNIQUE sem `WHERE deleted_at IS NULL` em tabela com soft delete; NUNCA FK sem índice cobrindo a leftmost.
---

# Database — O Portão (Postgres + asyncpg + dbmate)

Ponto de entrada único de banco. **NUNCA escreva código de DB sem passar por aqui.** A natureza da
tarefa decide qual reference descer; o checklist abaixo roteia. Os invariantes de stack (driver,
migrations) vivem na rule `backend.md`; aqui está a profundidade.

## Checklist de build (em ordem; só desça o que a tarefa exige)

- [ ] **1. Migration / schema** — vai escrever/revisar `.sql` em `db/migrations/`? (`CREATE TABLE`,
  `CREATE INDEX`, FK, `CHECK` em VARCHAR enum-like, GIN em JSONB, `UNIQUE` com soft delete, naming
  `ix_/ux_/uq_/ck_`). Disciplina + anti-bugs de índice/constraint → **`references/schema-discipline.md`**.
- [ ] **2. Repository / query** — vai escrever/editar `*_repository.py` ou montar SQL? (escolher
  fetch/fetchrow/fetchval/execute, contrato de input por operação, `$1/$2` parametrizado, `RETURNING`,
  COALESCE partial update, JSONB via codec, bulk, singleton, retorno dict/scalar) →
  **`references/asyncpg.md`**.
- [ ] **3. Migration tooling** — vai operar a ferramenta? (`dbmate new/up/migrate/rollback`, schema
  dump, squash/baseline, setup Docker/compose/CI, adoção em schema existente) → **`references/dbmate.md`**
  (que roteia pras sub-references em `references/dbmate/`).
- [ ] **4. Listagem paginada** — o endpoint devolve uma coleção? (`PagedResponse`, sentinela
  `LIMIT limit+1`, `total` exato em TODA página, whitelist de `ORDER BY`, desempate obrigatório por `id`,
  índice composto por chave de sort) → **`references/list-pagination.md`**.

## Invariantes não negociáveis (sempre)

- SQL **sempre** parametrizado `$1, $2` — **NUNCA** f-string (SQL injection). **Único carve-out**:
  interpolar (a) constante `Final` de módulo com o predicado `WHERE` e (b) fragmento de `ORDER BY`
  vindo de whitelist fechado (`SortMap`) — nenhum dos dois carrega dado de request, e todo VALOR segue
  em `$n`. Ver `references/list-pagination.md`.
- Lista: **NUNCA** `COUNT(*) OVER()` (o `WindowAgg` varre o filtro inteiro por página); **NUNCA**
  `ORDER BY` sem desempate por coluna única (com OFFSET, empate duplica/pula linha); **NUNCA**
  `total=len(items)`; **NUNCA** endpoint de coleção sem `LIMIT`.
- UPDATE parcial = verbose explícito + COALESCE — **NUNCA** dynamic SET clause.
- JSONB passa `dict`/`list` direto (pool codec orjson) — **NUNCA** `orjson.loads/dumps` manual.
- Repository retorna `dict`/`list[dict]`/scalar — **NUNCA** Pydantic (service faz `model_validate`).
- **NUNCA** índice em coluna PK (já existe). FK **SEMPRE** com índice (leftmost de algum índice).
- Tabela com soft delete → `UNIQUE` é partial `WHERE deleted_at IS NULL`.

## References

- `references/schema-discipline.md` — disciplina de schema/índice/constraint em migrations dbmate.
- `references/asyncpg.md` — repository pattern completo (method selection, SQL, JSONB, bulk, types).
- `references/dbmate.md` — dbmate (mental model, comandos, workflows) → `references/dbmate/{workflows,docker,postgres-patterns,squash}.md`.
- `references/list-pagination.md` — contrato de endpoint de lista (sentinela `LIMIT+1`, `total` em
  toda página, `SortMap` whitelist + desempate por `id`, índices compostos, carve-out da f-string).
