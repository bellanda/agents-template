---
name: dbmate
description: SQL-first database migration tool that uses plain .sql files. Use whenever the user is managing database schema changes with dbmate (creating, running, or rolling back migrations), setting up dbmate in a new project, integrating dbmate with Docker or CI/CD, squashing migrations into a baseline, or adopting dbmate as their migration tool. Trigger on mentions of "dbmate", "schema_migrations table", ".sql migration files", "migrate:up", "migrate:down", "DBMATE_*" environment variables, or when the user wants plain SQL migrations decoupled from any ORM or framework.
---

# dbmate

Ferramenta de migration que usa SQL puro em arquivos `.sql`. Binary único, agnóstico de linguagem e framework. Estado do schema rastreado em tabela no próprio DB.

## Quando consultar este skill

- Criar, modificar, aplicar ou reverter migrations.
- Setup inicial em projeto novo.
- Integração com Docker / docker-compose / CI/CD.
- Squash periódico (consolidar histórico de migrations em baseline única).
- Padrões específicos do Postgres (triggers, índices parciais, `CREATE INDEX CONCURRENTLY`, enums, JSONB).

## Mental model

dbmate é deliberadamente minimalista. Quatro características definem o produto:

| Aspecto              | Comportamento                                                             |
| -------------------- | ------------------------------------------------------------------------- |
| Arquivo de migration | `.sql` com blocos `-- migrate:up` e `-- migrate:down`                     |
| Tracking             | Tabela `schema_migrations` no próprio DB (1 linha por migration aplicada) |
| Ordem                | Linear via timestamp no nome do arquivo                                   |
| Configuração         | `DATABASE_URL` (env var) — não há config file                             |
| Schema dump          | Nativo (`dbmate dump` → `db/schema.sql`)                                  |
| Acoplamento          | Nenhum — funciona com qualquer linguagem ou framework                     |

**Implicação prática:** você escreve o SQL diretamente (não há autogenerate). Em troca, você ganha schema dump nativo, zero configuração e independência total de stack — a mesma ferramenta serve FastAPI, Axum, Fiber, Rails, Node, Go, etc.

## Como funciona internamente

### A tabela `schema_migrations`

Criada automaticamente no primeiro `dbmate up`:

```sql
CREATE TABLE schema_migrations (
  version VARCHAR(255) PRIMARY KEY
);
```

Cada migration aplicada insere uma linha cuja `version` é o **timestamp do nome do arquivo**. Apenas o número, não o conteúdo. Renomear o arquivo (preservando o timestamp) **não** afeta o estado aplicado.

Default: `schema_migrations`. Para customizar, use `--migrations-table` ou `DBMATE_MIGRATIONS_TABLE`.

### Naming dos arquivos

Formato: `[timestamp]_[descricao].sql` em `db/migrations/`.

```
db/migrations/20260502143501_create_users.sql
              └─── version ──┘ └── descrição ──┘
```

Só o **prefixo numérico** importa para tracking. `dbmate new` gera o timestamp automaticamente.

### Transações

Cada migration roda dentro de uma transação por padrão (em DBs que suportam — Postgres sim). Se algo falhar no meio, faz rollback.

Para casos que **não podem** rodar em transação (`CREATE INDEX CONCURRENTLY`, `ALTER TYPE ... ADD VALUE`, `VACUUM`), desligue na linha do header:

```sql
-- migrate:up transaction:false
CREATE INDEX CONCURRENTLY ix_users_email ON users(email);
```

### Schema file

A cada `dbmate up` ou `dbmate rollback`, dbmate regenera `db/schema.sql` — um dump completo do schema atual via `pg_dump --schema-only`. Esse arquivo:

- Deve ser commitado.
- Serve como documentação viva e diff visual do schema.
- Pode ser usado para bootstrap rápido de DB novo (`dbmate load`).

Para desligar o auto-dump: `--no-dump-schema` ou `DBMATE_NO_DUMP_SCHEMA=true`.

## Cheatsheet de comandos

| Comando                          | Efeito                                                         |
| -------------------------------- | -------------------------------------------------------------- |
| `dbmate new <descricao>`         | Cria arquivo `db/migrations/<timestamp>_<descricao>.sql` vazio |
| `dbmate up`                      | Cria DB se não existir + aplica todas as migrations pendentes  |
| `dbmate migrate`                 | Só aplica pendentes (não cria DB)                              |
| `dbmate rollback` (alias `down`) | Reverte a **última** migration aplicada                        |
| `dbmate status`                  | Mostra applied / pending                                       |
| `dbmate dump`                    | Regenera `db/schema.sql`                                       |
| `dbmate load`                    | Carrega `db/schema.sql` no DB (bootstrap rápido)               |
| `dbmate create` / `dbmate drop`  | Cria / dropa o DB inteiro                                      |
| `dbmate wait`                    | Bloqueia até DB ficar disponível (útil em containers)          |

Flags globais úteis:

| Flag                   | Quando usar                                                                                     |
| ---------------------- | ----------------------------------------------------------------------------------------------- |
| `--wait`               | Espera DB antes de rodar comando (em compose/CI)                                                |
| `--strict`             | Falha se houver migrations pendentes "fora de ordem" (timestamps anteriores ao último aplicado) |
| `--no-dump-schema`     | Não regenera schema.sql (em CI de teste, por exemplo)                                           |
| `-e TEST_DATABASE_URL` | Lê URL de outra env var (alterna entre dev/test)                                                |

## Configuração mínima

### `.env`

```env
DATABASE_URL=postgres://postgres:dev@localhost:5432/myapp?sslmode=disable
```

dbmate lê `.env` automaticamente do diretório atual. `sslmode=disable` é necessário para Postgres local sem TLS (default do dbmate é exigir TLS).

### Estrutura de pastas

```
project/
├── .env
├── db/
│   ├── migrations/
│   │   ├── 20260502143501_create_users.sql
│   │   └── 20260503090000_add_orders.sql
│   └── schema.sql              # gerado por dbmate, commitado
└── ...
```

## Workflows essenciais

Para cada workflow, há referência detalhada. Consulte conforme a tarefa:

- **Criar nova migration / estrutura interna do arquivo `.sql` / alterar tabela existente / rollback**: leia `references/workflows.md`.
- **Setup com Docker / docker-compose / CI**: leia `references/docker.md`.
- **Padrões Postgres** (triggers `updated_at`, índices parciais, `CONCURRENTLY`, enums, JSONB): leia `references/postgres-patterns.md`.
- **Squash de migrations em baseline única**: leia `references/squash.md`.

## Quick reference para tarefas comuns

### "Quero adicionar uma coluna nova"

```bash
dbmate new add_phone_to_users
```

Edite o arquivo:

```sql
-- migrate:up
ALTER TABLE users ADD COLUMN phone VARCHAR(50);

-- migrate:down
ALTER TABLE users DROP COLUMN phone;
```

```bash
dbmate up
```

Detalhes e edge cases (NOT NULL com default em tabela grande, renomeações, etc.) em `references/workflows.md`.

### "Como organizo o conteúdo do .sql quando tem várias tabelas"

Convenção: agrupar por tabela, ordem fixa dentro de cada bloco (`CREATE TABLE` → indexes → constraints → triggers), delimitador `===` de 60 caracteres, `migrate:down` em ordem reversa. Template completo e anti-patterns em `references/workflows.md` (seção "Estrutura interna do arquivo .sql").

### "Quero rodar migrations no Docker"

Padrão recomendado: serviço `migrate` no compose que roda **antes** do app, com healthcheck no DB. Esqueleto em `references/docker.md`.

### "Tenho 200 migrations e quero limpar"

Squash com baseline: `dbmate dump` → criar migration baseline → marcar como aplicada em ambientes existentes → apagar antigas. Procedimento passo-a-passo em `references/squash.md`.

### "Quero adotar dbmate em projeto que já tem schema"

Bootstrap a partir de schema existente: `pg_dump` do schema atual → vira primeira migration baseline do dbmate → marcar como aplicada nos ambientes que já têm o schema. Procedimento em `references/squash.md` (seção "Adoção em projeto com schema existente").

## Pontos de atenção (gotchas)

- **Sem autogenerate**: você escreve SQL na mão. Para schemas complexos (FKs, índices parciais, triggers), isso é um ganho — você tem controle total. Para schemas simples e mudanças triviais, é alguns segundos a mais por migration.
- **Ordem fora de sequência**: dbmate aplica pendentes em ordem numérica, mas **não bloqueia** uma migration com timestamp menor que o último aplicado. Use `--strict` (ou `DBMATE_STRICT=true`) em CI para falhar nesses casos.
- **Down migrations opcionais mas obrigatórias no arquivo**: o bloco `-- migrate:down` deve existir no arquivo (mesmo que vazio), mas só será executado se você rodar `dbmate rollback`. Em prod real, raramente se faz rollback — corrige-se com nova migration forward.
- **Schema dump exige binário do DB**: `dbmate dump` usa `pg_dump` (Postgres), `mysqldump` (MySQL), `sqlite3` (SQLite). Se não estiverem no `PATH`, dbmate **silenciosamente pula** o dump em `up`/`rollback`. Diagnostique com `dbmate dump` direto — vai mostrar o erro.
- **Conteúdo da migration não é guardado no DB**: só a `version`. Editar uma migration **já aplicada** em prod é ruim — o conteúdo novo nunca será reaplicado, e o histórico fica inconsistente entre ambientes. Regra: migration aplicada em qualquer ambiente compartilhado é imutável; correção = nova migration.
- **Múltiplos blocos no mesmo arquivo**: é permitido ter vários pares `migrate:up`/`migrate:down` no mesmo arquivo. O arquivo inteiro é tratado como uma unidade transacional. Útil para mudanças relacionadas que devem ser atômicas.

## Convenções recomendadas

- **Nomes descritivos** no `dbmate new`: `add_phone_to_users`, `create_orders_table`, `backfill_user_slugs`. Não `update_db` ou `fix`.
- **Estrutura interna do `.sql`**: agrupar por tabela, ordem fixa (table → indexes → constraints → triggers), delimitador `===`, `down` em ordem reversa. Template em `references/workflows.md`.
- **Sempre escrever o down** quando trivial (DROP COLUMN, DROP TABLE, DROP INDEX). Pular o down só quando for genuinamente irreversível (data backfill destrutivo, por exemplo) — e nesse caso, comentar o motivo dentro do bloco.
- **Migrations atômicas e pequenas**: uma mudança lógica por arquivo. Facilita rollback, code review e debug.
- **Índices em prod com `CONCURRENTLY`** + `transaction:false` em tabelas grandes — evita lock longo. Detalhes em `references/postgres-patterns.md`.
- **Commitar `db/schema.sql`**: é a documentação canônica do schema atual. Diff em PR mostra impacto de cada migration claramente.
