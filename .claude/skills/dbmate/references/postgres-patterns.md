# Padrões Postgres em migrations dbmate

Recipes prontas para os padrões mais comuns em projetos Postgres reais. Copie, adapte, cole.

## 1. Trigger automático de `updated_at`

Padrão clássico: coluna `updated_at TIMESTAMPTZ` que se atualiza sozinha em qualquer UPDATE.

### Função (uma vez por DB)

Coloque numa migration inicial. Toda tabela que tiver `updated_at` reusa essa função.

```sql
-- migrate:up
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- migrate:down
DROP FUNCTION IF EXISTS update_updated_at_column();
```

### Aplicar em uma tabela

```sql
-- migrate:up
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER update_users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW
  EXECUTE PROCEDURE update_updated_at_column();

-- migrate:down
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP TABLE users;
```

⚠️ **Não dropar `update_updated_at_column()`** no down de uma tabela específica — outras tabelas podem usar a mesma função.

## 2. Índices

### Índice simples

```sql
CREATE INDEX ix_orders_user_id ON orders(user_id);
```

### Índice único

```sql
CREATE UNIQUE INDEX ux_users_email ON users(email);
-- ou via constraint inline na tabela:
-- email VARCHAR(255) UNIQUE NOT NULL
```

### Índice composto

```sql
CREATE INDEX ix_orders_user_created
  ON orders(user_id, created_at DESC);
```

Ordem importa: bom para queries que filtram por `user_id` (com ou sem `created_at`), ruim para queries que filtram só por `created_at`.

### Índice parcial

Indexa só linhas que satisfazem um predicado. Reduz tamanho e melhora performance em queries que sempre filtram pelo mesmo critério.

```sql
-- Só indexa orders ativas
CREATE INDEX ix_orders_active
  ON orders(user_id, created_at)
  WHERE status NOT IN ('cancelled', 'completed');
```

### Índice em expressão

```sql
CREATE INDEX ix_users_lower_email ON users (LOWER(email));
-- Habilita: WHERE LOWER(email) = LOWER($1)
```

### Índice em campo JSONB

```sql
-- GIN para queries de containment (@>, ?, ?&, ?|)
CREATE INDEX ix_products_metadata_gin
  ON products USING GIN (metadata);

-- Btree em campo específico do JSONB
CREATE INDEX ix_products_brand
  ON products ((metadata->>'brand'));
```

### `CREATE INDEX CONCURRENTLY` (prod, tabelas grandes)

Não bloqueia escritas, mas não pode rodar em transação:

```sql
-- migrate:up transaction:false
CREATE INDEX CONCURRENTLY ix_orders_status ON orders(status);

-- migrate:down transaction:false
DROP INDEX CONCURRENTLY IF EXISTS ix_orders_status;
```

⚠️ Se `CREATE INDEX CONCURRENTLY` falhar (ex: constraint violada em índice unique), o índice fica em estado **inválido**. Detectar:

```sql
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
```

E dropar antes de tentar de novo:

```sql
DROP INDEX CONCURRENTLY IF EXISTS ix_orders_status;
```

## 3. Enum types

### Criar enum

```sql
-- migrate:up
CREATE TYPE order_status AS ENUM ('pending', 'paid', 'shipped', 'delivered', 'cancelled');

CREATE TABLE orders (
  id BIGSERIAL PRIMARY KEY,
  status order_status NOT NULL DEFAULT 'pending'
);

-- migrate:down
DROP TABLE orders;
DROP TYPE order_status;
```

### Adicionar valor a enum existente

⚠️ `ALTER TYPE ... ADD VALUE` **não pode rodar em transação**. Sempre `transaction:false`:

```sql
-- migrate:up transaction:false
ALTER TYPE order_status ADD VALUE 'refunded' AFTER 'cancelled';

-- migrate:down transaction:false
-- Postgres NÃO suporta remover valor de enum. Down é vazio ou recria o enum inteiro.
```

### Renomear valor de enum

Postgres ≥ 10:

```sql
-- migrate:up
ALTER TYPE order_status RENAME VALUE 'shipped' TO 'in_transit';

-- migrate:down
ALTER TYPE order_status RENAME VALUE 'in_transit' TO 'shipped';
```

### Alternativa: `VARCHAR + CHECK constraint`

Mais flexível que enum para evolução de valores. Padrão visto frequentemente em Postgres moderno:

```sql
CREATE TABLE orders (
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  CONSTRAINT ck_orders_status
    CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled'))
);
```

Para adicionar valor: drop e recria a constraint (rápido, em transação):

```sql
ALTER TABLE orders DROP CONSTRAINT ck_orders_status;
ALTER TABLE orders ADD CONSTRAINT ck_orders_status
  CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled', 'refunded'));
```

## 4. UUIDs

### `gen_random_uuid()` (Postgres ≥ 13, recomendado)

```sql
CREATE TABLE sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id BIGINT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL
);
```

`gen_random_uuid()` é built-in desde Postgres 13. Antes disso, precisava `CREATE EXTENSION pgcrypto`.

### UUIDv7 (timestamp-ordered)

Postgres 18+ tem `uuidv7()` nativo. Em versões anteriores, usa-se extensão ou função custom. Vantagem sobre v4: ordenação por tempo, melhor para índices b-tree.

```sql
CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT uuidv7(),
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 5. JSONB

### Coluna JSONB com default

```sql
CREATE TABLE products (
  id BIGSERIAL PRIMARY KEY,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  tags JSONB NOT NULL DEFAULT '[]'::JSONB
);
```

### Constraint em estrutura do JSONB

```sql
-- Garante que metadata sempre é objeto (não array nem null)
ALTER TABLE products
  ADD CONSTRAINT ck_products_metadata_is_object
  CHECK (jsonb_typeof(metadata) = 'object');
```

### Migração de dados em JSONB

```sql
-- Adicionar campo default a todos os registros existentes
UPDATE products
SET metadata = metadata || '{"version": 1}'::JSONB
WHERE NOT (metadata ? 'version');
```

## 6. Foreign keys com cascade strategies

```sql
-- ON DELETE CASCADE: apaga filhos junto
user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE

-- ON DELETE SET NULL: desfaz vínculo, mantém registro
created_by BIGINT REFERENCES users(id) ON DELETE SET NULL

-- ON DELETE RESTRICT (default): bloqueia delete do pai
order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE RESTRICT

-- ON DELETE NO ACTION: igual a RESTRICT mas verifica no fim da transação
```

Adicionar FK sem lock pesado em prod:

```sql
-- migrate:up
ALTER TABLE orders
  ADD CONSTRAINT fk_orders_user_id
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
  NOT VALID;

ALTER TABLE orders VALIDATE CONSTRAINT fk_orders_user_id;

-- migrate:down
ALTER TABLE orders DROP CONSTRAINT fk_orders_user_id;
```

`NOT VALID` adiciona a constraint sem checar registros existentes. `VALIDATE CONSTRAINT` checa em segundo plano (lock fraco).

## 7. Check constraints

```sql
CREATE TABLE products (
  price_cents BIGINT NOT NULL,
  CONSTRAINT ck_products_price_positive CHECK (price_cents >= 0)
);

-- ou adicionar depois:
ALTER TABLE products
  ADD CONSTRAINT ck_products_price_positive CHECK (price_cents >= 0);
```

Para tabela grande em prod, igual a FK — use `NOT VALID` + `VALIDATE`:

```sql
ALTER TABLE products
  ADD CONSTRAINT ck_products_price_positive CHECK (price_cents >= 0) NOT VALID;
ALTER TABLE products VALIDATE CONSTRAINT ck_products_price_positive;
```

## 8. Extensions

```sql
-- migrate:up
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- busca textual fuzzy
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- combinar tipos em GIN

-- migrate:down
-- Geralmente não dropa extensions — outras coisas podem depender.
```

## 9. Tabelas particionadas

```sql
-- migrate:up
CREATE TABLE events (
  id BIGSERIAL,
  occurred_at TIMESTAMPTZ NOT NULL,
  payload JSONB NOT NULL,
  PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE TABLE events_2026_01 PARTITION OF events
  FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE events_2026_02 PARTITION OF events
  FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

-- migrate:down
DROP TABLE events;
```

Criação de partições futuras geralmente é automatizada (cron job ou `pg_partman`), não em migration.

## 10. Materialized views

```sql
-- migrate:up
CREATE MATERIALIZED VIEW user_order_summary AS
SELECT
  u.id AS user_id,
  COUNT(o.id) AS total_orders,
  COALESCE(SUM(o.total_cents), 0) AS lifetime_cents
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
GROUP BY u.id
WITH DATA;

CREATE UNIQUE INDEX ux_user_order_summary_user_id
  ON user_order_summary(user_id);
-- UNIQUE necessário para REFRESH CONCURRENTLY

-- migrate:down
DROP MATERIALIZED VIEW user_order_summary;
```

Refresh em prod (não em migration — geralmente em job/cron):

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY user_order_summary;
```

## 11. Seeds (dados iniciais)

dbmate **não tem** comando de seed dedicado. Estratégias:

**Opção A: incluir na migration de criação da tabela.**

```sql
-- migrate:up
CREATE TABLE roles (
  id SERIAL PRIMARY KEY,
  name VARCHAR(64) UNIQUE NOT NULL
);

INSERT INTO roles (name) VALUES
  ('admin'),
  ('member'),
  ('viewer');

-- migrate:down
DROP TABLE roles;
```

**Opção B: migration dedicada de seed.**

```sql
-- migrate:up
INSERT INTO roles (name) VALUES ('admin'), ('member'), ('viewer')
ON CONFLICT (name) DO NOTHING;

-- migrate:down
-- Optional: DELETE FROM roles WHERE name IN (...);
```

`ON CONFLICT DO NOTHING` torna a migration idempotente — pode rodar duas vezes sem erro.

**Opção C: seeds fora do dbmate** (script Python/Node separado, rodado depois de migrations). Recomendado para seeds que mudam frequentemente ou dependem de ambiente.

## 12. Resumo de operações que exigem `transaction:false`

| Operação | Por quê |
|---|---|
| `CREATE INDEX CONCURRENTLY` | Não pode rodar em transação |
| `DROP INDEX CONCURRENTLY` | Idem |
| `ALTER TYPE ... ADD VALUE` | Idem (Postgres < 12) |
| `VACUUM` / `REINDEX` | Não funciona em transação |
| `CREATE DATABASE` / `DROP DATABASE` | Idem |
| `ALTER SYSTEM` | Idem |

Sintaxe:

```sql
-- migrate:up transaction:false
<comando>
```

⚠️ Sem transação, falha no meio deixa o DB em estado intermediário. Use com cuidado e idealmente uma operação por arquivo.
