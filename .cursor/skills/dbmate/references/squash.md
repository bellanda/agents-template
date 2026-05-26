# Squash de migrations + adoção em DB existente

Os dois procedimentos são quase idênticos — ambos consistem em **criar uma migration baseline única que representa o schema atual**, e marcá-la como aplicada nos ambientes que já têm o schema. A diferença está apenas no estado inicial:

- **Squash periódico** — projeto que já usa dbmate há tempo, acumulou centenas de migrations, e quer consolidar.
- **Adoção em DB existente** — projeto que tem schema rodando em prod (criado manualmente, via outra ferramenta, ou via SQL ad-hoc) e está adotando dbmate agora.

## Conceito

Após meses/anos de migrations, a pasta `migrations/` acumula. Em ambientes existentes (prod), tudo já foi aplicado e está estável. Em ambientes novos (CI, dev novo), cada `dbmate up` re-roda 200+ migrations sequencialmente — desnecessário.

**Solução: squash.**

```
ANTES:                          DEPOIS:
db/migrations/                  db/migrations/
├── 20240101_initial.sql        └── 20260502_baseline.sql  ← 1 só
├── 20240115_add_orders.sql
├── 20240203_add_payments.sql
├── ... (× 197 mais)
└── 20260501_add_index.sql
```

A baseline contém o schema **inteiro** consolidado. Em ambientes novos, roda só ela. Em ambientes existentes, marca-se como aplicada (sem rodar) e apaga as antigas.

## 1. Squash periódico

### Pré-requisitos

- **Todos** os ambientes (dev, staging, prod) estão no mesmo head — ninguém tem migration pendente.
- Você tem acesso ao DB de prod (psql) para marcar a baseline como aplicada.
- Janela de manutenção curta acordada (não há deploy de migration em andamento).

### Procedimento

#### Passo 1 — Branch dedicada

```bash
git checkout -b chore/squash-migrations-2026-05
```

#### Passo 2 — Garantir que tudo está aplicado

Em **todos** os ambientes:

```bash
dbmate status
# Deve mostrar [X] em todas as migrations, nenhum [ ]
```

#### Passo 3 — Gerar schema dump consolidado

```bash
dbmate dump
```

Isso atualiza `db/schema.sql` com o estado atual canônico do schema.

#### Passo 4 — Criar a migration baseline

```bash
dbmate new baseline
```

Gera `db/migrations/<TIMESTAMP_NOVO>_baseline.sql`. Anote o `<TIMESTAMP_NOVO>` — vai precisar dele.

Edite o arquivo. O conteúdo do bloco `migrate:up` é o `db/schema.sql` filtrado:

```sql
-- migrate:up

-- (Cole aqui o conteúdo de db/schema.sql, REMOVENDO:)
-- 1. Linhas SET (configurações de sessão do pg_dump)
-- 2. Comentários "-- Dumped from..."
-- 3. CREATE SCHEMA public (já existe)
-- 4. ALTER SCHEMA OWNER (não relevante)
-- 5. A tabela schema_migrations e seus INSERTs (dbmate gerencia)

CREATE TABLE users (...);
CREATE TABLE orders (...);
-- ... resto do schema

-- migrate:down

-- Baseline é "ponto zero". Down dropa tudo (raramente usado em prod):
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS users CASCADE;
-- ... etc
DROP FUNCTION IF EXISTS update_updated_at_column();
```

#### Passo 5 — Validar a baseline em DB limpo

```bash
# Cria DB de teste
createdb myapp_squash_test

# Aplica só a baseline
DATABASE_URL=postgres://localhost/myapp_squash_test?sslmode=disable \
  dbmate up

# Compara schemas
pg_dump --schema-only myapp_squash_test > /tmp/from_baseline.sql
pg_dump --schema-only myapp > /tmp/from_history.sql
diff /tmp/from_baseline.sql /tmp/from_history.sql
```

Se houver diff, a baseline não está fiel ao histórico. Ajuste o `migrate:up` até o diff ficar limpo.

#### Passo 6 — Marcar baseline como aplicada nos ambientes existentes

Em **cada ambiente** (dev, staging, prod), na ordem dev → staging → prod:

```sql
BEGIN;

-- Limpa histórico antigo
DELETE FROM schema_migrations;

-- Marca a baseline como aplicada
INSERT INTO schema_migrations (version) VALUES ('<TIMESTAMP_NOVO>');

COMMIT;
```

Em prod, **dump completo do DB antes** disso. Sempre.

#### Passo 7 — Apagar migrations antigas do repo

```bash
cd db/migrations/
ls *.sql | grep -v baseline | xargs git rm
git add baseline.sql
git commit -m "Squash migrations into baseline (2026-05)"
```

#### Passo 8 — Validar

Em ambiente novo (CI ou dev fresh):

```bash
dbmate drop
dbmate up
# Deve aplicar SÓ a baseline
```

Em ambiente existente:

```bash
dbmate status
# Deve mostrar [X] na baseline e nenhuma pendente
```

### Frequência recomendada

A cada 6–12 meses, ou quando passar de ~100 migrations. Não há urgência — squash é otimização, não obrigação.

## 2. Adoção em projeto com schema existente

Caso de uso: você tem um DB rodando em prod cujo schema foi criado manualmente, via scripts SQL ad-hoc, ou via outra ferramenta de migration. Quer começar a usar dbmate sem perder o estado.

A estratégia é a mesma do squash: gerar uma migration baseline a partir do schema atual e marcá-la como aplicada nos ambientes que já têm o schema.

### Pré-requisitos

- Você tem `pg_dump` (ou equivalente do seu DB) instalado e acessível.
- Acesso de leitura ao schema atual de prod.
- Acesso ao DB para criar a tabela `schema_migrations` e marcar a baseline.

### Procedimento

#### Passo 1 — Instalar dbmate

```bash
brew install dbmate
# ou: npm install --save-dev dbmate
# ou: docker pull ghcr.io/amacneil/dbmate:latest
```

#### Passo 2 — Configurar `.env`

```env
DATABASE_URL=postgres://user:pass@localhost:5432/myapp?sslmode=disable
```

#### Passo 3 — Dump do schema atual via `pg_dump`

dbmate ainda não foi inicializado, então use `pg_dump` direto:

```bash
pg_dump --schema-only --no-owner --no-privileges \
  $DATABASE_URL > /tmp/schema_raw.sql
```

#### Passo 4 — Limpar o dump

Remova:

- Linhas `SET ...` (configurações de sessão do pg_dump)
- Comentários `-- Dumped from database version ...`
- `CREATE SCHEMA public` (já existe)
- `ALTER SCHEMA public OWNER TO ...`
- Qualquer tabela de tracking de outra ferramenta de migration que estiver no schema (se houver — ela vai ser substituída por `schema_migrations`).

Script para limpeza automatizada (cobre os comuns):

```bash
sed -E '
  /^SET /d
  /^SELECT pg_catalog\.set_config/d
  /^-- Dumped/d
  /^-- Started on/d
  /^-- Completed on/d
  /^CREATE SCHEMA public;$/d
  /^ALTER SCHEMA public OWNER/d
' /tmp/schema_raw.sql > /tmp/schema_clean.sql
```

Revise o resultado manualmente — automação não pega tudo, especialmente tabelas de tracking de ferramentas anteriores.

#### Passo 5 — Estrutura inicial dbmate

```bash
mkdir -p db/migrations
```

#### Passo 6 — Criar a baseline

```bash
dbmate new baseline
```

Pegue o timestamp gerado (vai estar em `db/migrations/<TIMESTAMP>_baseline.sql`).

Edite o arquivo:

```sql
-- migrate:up
-- (cole o conteúdo de /tmp/schema_clean.sql aqui)

-- migrate:down
-- DROPs apropriados, na ordem reversa de dependências
```

#### Passo 7 — Validar em DB de teste

```bash
createdb myapp_dbmate_test
DATABASE_URL=postgres://localhost/myapp_dbmate_test?sslmode=disable dbmate up
pg_dump --schema-only myapp_dbmate_test > /tmp/from_baseline.sql
pg_dump --schema-only myapp > /tmp/from_existing.sql
diff /tmp/from_baseline.sql /tmp/from_existing.sql
```

Diff vazio = baseline fiel.

#### Passo 8 — Marcar baseline como aplicada nos ambientes existentes

Em cada ambiente (dev → staging → prod):

```sql
BEGIN;

-- Cria a tabela schema_migrations (não existe ainda)
CREATE TABLE IF NOT EXISTS schema_migrations (
  version VARCHAR(255) PRIMARY KEY
);

-- Marca a baseline como aplicada
INSERT INTO schema_migrations (version) VALUES ('<TIMESTAMP_BASELINE>');

-- Opcional: dropar tabelas de tracking de ferramenta anterior, se houver
-- DROP TABLE IF EXISTS <tabela_de_tracking_antiga>;

COMMIT;
```

Backup de prod **antes**.

#### Passo 9 — Configurar pipeline e Docker

Adicione `dbmate up` (ou `dbmate migrate`) em:

- `Dockerfile` / `docker-compose.yml` (ver `docker.md`)
- Pipelines de CI/CD (etapa antes do deploy do app)
- Scripts locais de bootstrap (`Makefile`, etc.)

#### Passo 10 — Daqui pra frente

Nova migration:

```bash
dbmate new add_phone_to_users
# edita db/migrations/<TIMESTAMP>_add_phone_to_users.sql
dbmate up
```

### Custo total estimado

- Projeto pequeno/médio (1 schema, ~30 tabelas): **uma tarde**.
- Projeto grande (múltiplos schemas, dezenas de objetos custom como triggers, partições, materialized views): **1–2 dias**, principalmente revisando o dump e adaptando padrões custom.

## 3. Pontos de atenção comuns aos dois procedimentos

| Ponto | Detalhe |
|---|---|
| **Backup antes** | Sempre. Em prod, `pg_dump` completo + snapshot de filesystem se possível. |
| **Ordem dos ambientes** | Dev → staging → prod. Nunca prod primeiro. |
| **Baseline irreversível?** | Não — escreva o `migrate:down` com DROPs apropriados. Mas em prod raramente se executa. |
| **Diff zero não é garantia** | Mesmo com diff de schema vazio, dados, sequences, owners e privilégios podem diferir. Em prod, valide queries da app rodando contra ambiente staging migrado. |
| **Branches longas** | Se algum dev tem branch com migrations antigas pendentes, ela vai conflitar com a baseline. Coordene com o time antes do squash — todas as migrations pendentes em branches devem ser mergeadas ou descartadas. |
| **CI cache** | Se CI cacheia DBs, invalide o cache pós-squash — DBs cacheados ainda têm `schema_migrations` antiga. |
