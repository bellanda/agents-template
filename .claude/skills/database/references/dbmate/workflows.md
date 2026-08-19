# Workflows do dbmate

Cobertura completa dos fluxos do dia-a-dia. Cada seção é independente — pule direto para a tarefa.

## 1. Criar uma nova migration

```bash
dbmate new <descricao_em_snake_case>
```

Gera `db/migrations/<timestamp>_<descricao>.sql` com template vazio:

```sql
-- migrate:up


-- migrate:down

```

Edite preenchendo os dois blocos. O bloco `migrate:down` deve existir mesmo se vazio.

### Exemplo: criar tabela

```sql
-- migrate:up
CREATE TABLE orders (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  total_cents BIGINT NOT NULL CHECK (total_cents >= 0),
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_orders_user_id ON orders(user_id);
CREATE INDEX ix_orders_status ON orders(status);

-- migrate:down
DROP TABLE orders;
```

Aplicar:

```bash
dbmate up
```

Output esperado:

```
Applying: 20260502143501_create_orders.sql
Applied: 20260502143501_create_orders.sql in 12ms
Writing: ./db/schema.sql
```

## 2. Estrutura interna do arquivo .sql

Convenção para arquivos com múltiplas mudanças (típico do `initial.sql` ou de migrations que tocam várias tabelas).

### Princípio: agrupar por tabela

Cada tabela é uma seção delimitada. Mexer em `users` mexe num só lugar; reviewer lê "tudo de `users`" como bloco coeso, não pula entre 200 linhas espalhadas.

### Ordem fixa dentro da seção de tabela

Dentro de cada bloco de tabela, a ordem é:

1. `CREATE TABLE`
2. `CREATE INDEX` (todos os índices da tabela)
3. `ALTER TABLE ADD CONSTRAINT` (constraints não-inline — as inline ficam no `CREATE TABLE`)
4. `CREATE TRIGGER`

A ordem não é estética — é dependência. Index pode referenciar coluna; constraint pode referenciar coluna; trigger pode referenciar coluna e função. Inverter quebra com `relation does not exist` ou `column does not exist`.

### Delimitador

Use linha de `=` com 60 caracteres como header de seção. Sem ASCII art elaborada — fica inconsistente entre devs.

### Template completo

```sql
-- migrate:up

-- ============================================================
-- Extensions & shared functions
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- users
-- ============================================================

-- Table
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE UNIQUE INDEX ux_users_email ON users(email);
CREATE INDEX ix_users_status ON users(status) WHERE status != 'deleted';

-- Constraints
ALTER TABLE users ADD CONSTRAINT ck_users_email_format
  CHECK (email ~ '^.+@.+\..+$');

-- Triggers
CREATE TRIGGER update_users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- ============================================================
-- organizations
-- ============================================================

-- Table
CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  owner_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX ix_organizations_owner_id ON organizations(owner_id);

-- Triggers
CREATE TRIGGER update_organizations_updated_at
  BEFORE UPDATE ON organizations
  FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- ============================================================
-- vehicles  (depends on: users, organizations)
-- ============================================================

-- ... (mesma estrutura)

-- migrate:down

-- ============================================================
-- vehicles
-- ============================================================

DROP TABLE IF EXISTS vehicles CASCADE;

-- ============================================================
-- organizations
-- ============================================================

DROP TRIGGER IF EXISTS update_organizations_updated_at ON organizations;
DROP TABLE IF EXISTS organizations CASCADE;

-- ============================================================
-- users
-- ============================================================

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP TABLE IF EXISTS users CASCADE;

-- ============================================================
-- Shared
-- ============================================================

DROP FUNCTION IF EXISTS update_updated_at_column();
```

### `migrate:down` em ordem reversa

A ordem das seções no down é o **inverso** do up. Tabelas dependentes são dropadas primeiro, função compartilhada por último. Comente dependências no header da seção do up (`-- vehicles  (depends on: users, organizations)`) — facilita visualizar a ordem reversa correta.

### Migration incremental (uma única mudança)

Estrutura mais leve. Mantém o agrupamento por tabela, sem o overhead de múltiplas seções:

```sql
-- migrate:up

-- ============================================================
-- vehicles: telemetry tracking
-- ============================================================

ALTER TABLE vehicles ADD COLUMN last_telemetry_at TIMESTAMPTZ;

CREATE INDEX ix_vehicles_last_telemetry_at
  ON vehicles(last_telemetry_at)
  WHERE last_telemetry_at IS NOT NULL;

-- migrate:down

ALTER TABLE vehicles DROP COLUMN last_telemetry_at;
```

O header descritivo (`vehicles: telemetry tracking`) explica o **propósito** da migration, não só a tabela afetada — útil em PR review.

### Quando comentar (e quando não)

Comentário existe para explicar **decisão não-óbvia**. Sempre que o "porquê" não é evidente do código, comente:

```sql
-- Partial index: vendas representam ~5% das linhas, índice cheio é desperdício
CREATE INDEX ix_vehicles_sold_at
  ON vehicles(sold_at)
  WHERE status = 'vendido';

-- JSONB em vez de tabela separada porque dados nunca são consultados
-- isoladamente, sempre carregados junto com o vehicle
ALTER TABLE vehicles ADD COLUMN extra_metadata JSONB NOT NULL DEFAULT '{}';
```

NÃO comente o óbvio. Os exemplos abaixo são ruído — adicionam linhas sem informação:

```sql
-- BAD: nome da coluna já documenta
email VARCHAR(255) NOT NULL,  -- email do usuário

-- BAD: o CREATE TABLE está logo abaixo
-- create users table
CREATE TABLE users (...);

-- BAD: duplicado no git blame e no commit message
-- Author: João, Date: 2026-05-02, Ticket: PROJ-123
```

### Anti-patterns nesta convenção

| Anti-pattern                                                                                     | Por quê evitar                                                       |
| ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| Numeração explícita das seções (`-- 1. users`, `-- 2. organizations`)                            | Quebra ao reordenar/inserir tabelas. O delimitador `===` já delimita |
| Header gigante no topo do arquivo (autor, data, ticket)                                          | Já está no git blame e commit message. Duplicação que envelhece mal  |
| ASCII art elaborada nos delimitadores                                                            | Custom de cada dev, vira inconsistência ao longo do tempo            |
| Misturar índices, constraints e triggers de várias tabelas em "seções globais" no fim do arquivo | Quebra o princípio de agrupamento. Reviewer perde o contexto         |

## 3. Alterar tabela existente

### Adicionar coluna nullable (seguro)

```sql
-- migrate:up
ALTER TABLE users ADD COLUMN phone VARCHAR(50);

-- migrate:down
ALTER TABLE users DROP COLUMN phone;
```

### Adicionar coluna NOT NULL com default

Em tabela grande, isso pode bloquear. Postgres ≥ 11 faz `ADD COLUMN ... DEFAULT` instantaneamente para constants — não reescreve a tabela. Mas para defaults voláteis (`now()`, `gen_random_uuid()`), **reescreve**. Estratégia segura para prod:

```sql
-- migrate:up

-- 1) Adiciona como nullable
ALTER TABLE users ADD COLUMN status VARCHAR(32);

-- 2) Backfill em batches (ou inline se tabela for pequena)
UPDATE users SET status = 'active' WHERE status IS NULL;

-- 3) Aplica NOT NULL e default
ALTER TABLE users ALTER COLUMN status SET DEFAULT 'active';
ALTER TABLE users ALTER COLUMN status SET NOT NULL;

-- migrate:down
ALTER TABLE users DROP COLUMN status;
```

Para tabelas **muito** grandes, separe o backfill em uma migration própria (idealmente fora de transação ou em batches via app).

### Renomear coluna

```sql
-- migrate:up
ALTER TABLE users RENAME COLUMN name TO full_name;

-- migrate:down
ALTER TABLE users RENAME COLUMN full_name TO name;
```

⚠️ Renomear quebra apps que ainda usam o nome antigo. Em prod com zero-downtime, faça em 3 passos (em migrations separadas, ao longo de deploys):

1. Adiciona coluna nova, copia dados, mantém antiga.
2. App passa a escrever nas duas, lê da nova.
3. Remove a antiga.

### Drop coluna

```sql
-- migrate:up
ALTER TABLE users DROP COLUMN deprecated_field;

-- migrate:down
ALTER TABLE users ADD COLUMN deprecated_field VARCHAR(255);
-- Aviso: dados perdidos no up são irrecuperáveis no down
```

### Alterar tipo de coluna

```sql
-- migrate:up
ALTER TABLE products
  ALTER COLUMN price TYPE NUMERIC(12, 2)
  USING price::NUMERIC(12, 2);

-- migrate:down
ALTER TABLE products
  ALTER COLUMN price TYPE INTEGER
  USING price::INTEGER;
```

Tipo cast pode reescrever a tabela (lock pesado em prod). Para tabelas grandes, prefira coluna nova + backfill + swap.

### Adicionar índice em prod

**Sempre** com `CONCURRENTLY` + `transaction:false`:

```sql
-- migrate:up transaction:false
CREATE INDEX CONCURRENTLY ix_orders_created_at ON orders(created_at);

-- migrate:down transaction:false
DROP INDEX CONCURRENTLY IF EXISTS ix_orders_created_at;
```

`CONCURRENTLY` permite escritas durante criação. Sem isso, lock exclusivo bloqueia INSERTs/UPDATEs até terminar.

### Adicionar foreign key sem lock

FK adicionada normalmente valida toda a tabela em lock. Em prod com tabela grande:

```sql
-- migrate:up
-- 1) Adiciona constraint NOT VALID (não valida dados existentes)
ALTER TABLE orders
  ADD CONSTRAINT fk_orders_user_id FOREIGN KEY (user_id)
  REFERENCES users(id) NOT VALID;

-- 2) Valida em segundo plano (lock fraco)
ALTER TABLE orders VALIDATE CONSTRAINT fk_orders_user_id;

-- migrate:down
ALTER TABLE orders DROP CONSTRAINT fk_orders_user_id;
```

## 4. Aplicar migrations

```bash
dbmate up         # cria DB se não existir + aplica pending + regenera schema.sql
dbmate migrate    # só aplica pending (não cria DB nem regenera schema)
```

Use `dbmate up` em dev. Use `dbmate migrate` em prod / CI quando o DB já existe e você quer só aplicar.

### Verificar estado

```bash
dbmate status
```

Output:

```
[X] 20260101000000_initial.sql
[X] 20260201000000_add_orders.sql
[ ] 20260301000000_add_payments.sql
```

`[X]` = aplicada, `[ ]` = pendente.

Para uso em script (exit code 0 se nada pendente, não-zero se houver):

```bash
dbmate status --exit-code --quiet
```

## 5. Rollback

```bash
dbmate rollback   # reverte última aplicada
dbmate down       # alias
```

`dbmate rollback` reverte **uma só** — não há `rollback -n 5`. Para reverter várias, rode em loop (apenas em dev — em prod, raramente se faz rollback; corrige-se com forward migration).

```bash
# Rollback de 3 em dev
for i in 1 2 3; do dbmate rollback; done
```

⚠️ **Nunca** rollback em prod sem certeza absoluta. O bloco `migrate:down` raramente é testado tão bem quanto o `migrate:up`. Estratégia padrão: bug em prod → nova migration que conserta forward, não rollback.

## 6. Schema dump e load

### Regenerar schema.sql

```bash
dbmate dump
```

Equivale a `pg_dump --schema-only --no-owner` filtrado e formatado. Sobrescreve `db/schema.sql`. Já roda automaticamente após `up` e `rollback` (a menos que `--no-dump-schema`).

### Bootstrap rápido a partir de schema.sql

```bash
dbmate load
```

Equivale a `psql < db/schema.sql`. Útil em test harness ou setup inicial — é muito mais rápido que rodar 200 migrations sequencialmente.

⚠️ `dbmate load` **não** aplica migrations pendentes. Workflow típico em CI de teste:

```bash
dbmate drop          # limpa
dbmate create        # cria DB vazio
dbmate load          # aplica schema.sql consolidado
# (não precisa rodar migrate, schema.sql já contém schema_migrations populado)
```

## 7. Múltiplos blocos no mesmo arquivo

Útil para agrupar mudanças relacionadas que devem ser atômicas:

```sql
-- migrate:up
CREATE TABLE users (id SERIAL PRIMARY KEY);

-- migrate:down
DROP TABLE users;

-- migrate:up
ALTER TABLE users ADD COLUMN email VARCHAR;

-- migrate:down
ALTER TABLE users DROP COLUMN email;
```

O arquivo inteiro é uma transação. Se qualquer bloco falhar, **tudo** é revertido.

## 8. Trabalhando com múltiplos ambientes

`.env`:

```env
DATABASE_URL=postgres://localhost/myapp_dev?sslmode=disable
TEST_DATABASE_URL=postgres://localhost/myapp_test?sslmode=disable
```

```bash
dbmate up                              # usa DATABASE_URL
dbmate -e TEST_DATABASE_URL up         # usa TEST_DATABASE_URL
dbmate -u "postgres://..." up          # URL inline (ignora env)
```

Padrão útil para testes:

```bash
# Recria DB de teste do zero (rápido via load)
dbmate -e TEST_DATABASE_URL drop
dbmate -e TEST_DATABASE_URL --no-dump-schema up
```

## 9. Resolução de problemas comuns

| Problema                                      | Causa                                                        | Solução                                                            |
| --------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------ |
| `database "myapp" does not exist`             | DB não foi criado                                            | `dbmate create` ou `dbmate up` (cria automaticamente)              |
| `relation "schema_migrations" does not exist` | Primeira execução                                            | Normal — `dbmate up` cria a tabela                                 |
| `dbmate dump` silenciosamente pulado          | `pg_dump` não no PATH                                        | Instale `postgresql-client` (versão ≥ a do servidor)               |
| Migration aplicada não aparece em `status`    | Timestamp diferente do que está no DB                        | Verifique `SELECT * FROM schema_migrations;`                       |
| "out of order" warning                        | Migration pendente com timestamp anterior ao último aplicado | Aceite (default) ou use `--strict` para falhar                     |
| Migration trava                               | Lock em tabela                                               | Verifique `pg_stat_activity` — pode ser query longa segurando lock |

## 10. Anti-patterns a evitar

- **Editar migration já aplicada em ambiente compartilhado.** O conteúdo novo nunca será reaplicado. Crie nova migration que conserta.
- **Migration gigante com 50 mudanças.** Difícil de revisar, difícil de fazer rollback parcial. Quebre em arquivos menores e atômicos.
- **`DROP TABLE x; CREATE TABLE x` para "renomear" coluna.** Perde dados. Use `ALTER TABLE RENAME COLUMN`.
- **Backfill inline em tabela grande.** Trava a tabela. Faça em batches via app ou em migration `transaction:false` com `UPDATE ... LIMIT`.
- **Esquecer `CONCURRENTLY` em índice de prod.** Bloqueia escritas até terminar. Sempre `CREATE INDEX CONCURRENTLY` + `transaction:false` em tabelas com tráfego.
- **Mudança de schema + data migration no mesmo arquivo em prod.** Se data migration falhar, schema fica num meio-termo. Separe em duas migrations.
