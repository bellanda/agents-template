---
name: db-schema-discipline
description: Disciplina de schema Postgres em migrations dbmate — índice automático de PK (NUNCA recriar), FK SEMPRE com índice (leftmost de algum índice, senão dedicated `ix_<tabela>_<coluna>`), CHECK constraints em VARCHAR enum-like espelhando StrEnum/frozenset do código, GIN só em JSONB consultado por conteúdo (`@>`, `?`, `?|`, `?&`) e B-Tree de expressão para extração (`->>`, `#>>`), partial UNIQUE index `WHERE deleted_at IS NULL` para soft-delete, naming convention `ix_/ux_/uq_/ck_`. INVOCAR ANTES de — escrever qualquer `.sql` em `db/migrations/`, criar `CREATE TABLE`, adicionar `CREATE INDEX`, adicionar FK, criar VARCHAR que espelha enum no Python, adicionar `UNIQUE` em tabela com soft delete, criar índice em JSONB, ou revisar migration que outra pessoa escreveu. NUNCA criar índice em coluna PK (já existe); NUNCA `UNIQUE` sem `WHERE deleted_at IS NULL` se a tabela tem soft delete; NUNCA FK sem índice cobrindo a coluna leftmost.
---

# DB Schema & Index Discipline (Postgres + dbmate)

Disciplina aplicada a toda migration em `db/migrations/*.sql`. Esses invariantes evitam classes inteiras de bug em produção (sequential scan em delete cascade, recadastro bloqueado por linha soft-deletada, índice GIN em coluna errada, write amplification).

## 1. Índice de PK é automático — NUNCA recrie

Postgres cria índice único (B-Tree) automaticamente para `PRIMARY KEY`. Recriar gera write amplification (toda INSERT/UPDATE escreve em 2 índices em vez de 1) sem benefício.

```sql
-- BAD
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ...
);
CREATE INDEX ix_users_id ON users(id);   -- ❌ REDUNDANTE

-- GOOD
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ...
);
-- nada mais — o índice de PK já existe
```

Mesmo para PK composta: o `PRIMARY KEY (a, b)` cria índice `(a, b)`. Não recrie.

## 2. Toda FK tem que ser leftmost de algum índice

Postgres **não** indexa colunas FK automaticamente. Sem índice cobrindo a coluna FK:

- `DELETE`/`UPDATE` no pai → sequential scan no filho (pra checar CASCADE/SET NULL).
- Em tabelas grandes, isso vira deadlock ou timeout.

Regra: a coluna FK precisa ser **leftmost** de algum índice. Se já é leftmost de um composto, ok. Senão, índice dedicado.

```sql
-- GOOD: FK leftmost em índice composto
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    body TEXT NOT NULL
);
CREATE INDEX ix_messages_conversation_id_created_at
    ON messages(conversation_id, created_at DESC);
-- ✅ conversation_id é leftmost — cobre FK + query de timeline

-- GOOD: índice dedicado quando não tem composto adequado
CREATE TABLE notifications (
    id UUID PRIMARY KEY,
    recipient_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    payload JSONB NOT NULL
);
CREATE INDEX ix_notifications_recipient_user_id ON notifications(recipient_user_id);
-- ✅ dedicado pq não há outra query que justifique composto

-- BAD: FK sem índice
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE
);
-- ❌ DELETE em customers → seq scan em orders
```

## 3. CHECK constraint em coluna enum-like

Toda `VARCHAR` que espelha um `StrEnum`/`frozenset`/conjunto fechado de constantes Python ganha `CHECK`. Valores no SQL espelham o enum do código — manutenção pareada (mudou enum → atualiza migration).

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    status VARCHAR(20) NOT NULL,
    channel VARCHAR(20) NOT NULL,
    CONSTRAINT ck_conversations_status
        CHECK (status IN ('open', 'waiting', 'closed', 'archived')),
    CONSTRAINT ck_conversations_channel
        CHECK (channel IN ('whatsapp', 'instagram', 'facebook', 'webchat'))
);
```

```python
# backend/src/api/models/conversation/conversation_jsonb.py
from enum import StrEnum

class ConversationStatus(StrEnum):
    OPEN = "open"
    WAITING = "waiting"
    CLOSED = "closed"
    ARCHIVED = "archived"
```

Naming: `ck_<tabela>_<coluna>` distintivo e greppable.

## 4. GIN só em JSONB consultado por conteúdo

GIN é caro de manter (índice secundário grande, write amplification). Vale a pena **apenas** para query containment/key existence:

| Query pattern              | Beneficia GIN? | Use                                      |
| -------------------------- | -------------- | ---------------------------------------- |
| `metadata @> '{"k":"v"}'`  | ✅              | `CREATE INDEX ... USING GIN (metadata)`  |
| `metadata ? 'key'`         | ✅              | `CREATE INDEX ... USING GIN (metadata)`  |
| `metadata ?\| ARRAY[...]`  | ✅              | `CREATE INDEX ... USING GIN (metadata)`  |
| `metadata ?& ARRAY[...]`   | ✅              | `CREATE INDEX ... USING GIN (metadata)`  |
| `metadata->>'k' = 'v'`     | ❌              | B-Tree de expressão na chave             |
| `metadata#>>'{a,b}' = 'v'` | ❌              | B-Tree de expressão no path              |
| `jsonb_array_elements(...)` no WHERE | ❌    | redesenha schema ou tabela auxiliar      |

```sql
-- GOOD: GIN para containment
CREATE INDEX ix_conversations_metadata_gin
    ON conversations USING GIN (metadata)
    WHERE deleted_at IS NULL;

-- GOOD: B-Tree de expressão para extração quente
CREATE INDEX ix_conversations_metadata_external_id
    ON conversations ((metadata->>'external_id'))
    WHERE deleted_at IS NULL;
```

Só cria índice (de qualquer tipo) se o WHERE é **quente** — query rodando muitas vezes por minuto. Senão, planner escolhe seq scan e tudo bem.

## 5. Soft delete + UNIQUE = partial unique index

Se a tabela carrega `deleted_at TIMESTAMPTZ`, todo `UNIQUE` precisa filtrar `WHERE deleted_at IS NULL`. Caso contrário, linha "morta" bloqueia recadastro de novo registro com mesmo valor.

```sql
-- BAD: UNIQUE absoluto bloqueia recadastro de email reusado
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,   -- ❌
    deleted_at TIMESTAMPTZ
);
-- → user deleta conta, tenta recriar com mesmo email → constraint violation

-- GOOD: partial unique index
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    deleted_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX ux_users_email_active
    ON users(email)
    WHERE deleted_at IS NULL;
-- ✅ user soft-deletado libera o email para reuso
```

Multi-tenant: `(organization_id, slug)` com partial:

```sql
CREATE UNIQUE INDEX ux_workspaces_org_slug_active
    ON workspaces(organization_id, slug)
    WHERE deleted_at IS NULL;
```

## 6. Naming convention

| Prefixo | O que é                          | Exemplo                                       |
| ------- | -------------------------------- | --------------------------------------------- |
| `ix_`   | Índice comum (B-Tree, GIN, etc.) | `ix_messages_conversation_id_created_at`      |
| `ux_`   | Unique INDEX                     | `ux_users_email_active`                       |
| `uq_`   | UNIQUE constraint inline         | `CONSTRAINT uq_orgs_external_id UNIQUE (...)` |
| `ck_`   | CHECK constraint                 | `ck_conversations_status`                     |

Greppable: `rg "ix_users_"` → todos índices envolvendo `users`. Não use nomes auto-gerados pelo Postgres (`users_email_key`) — opacos.

## 7. Template de migration (dbmate)

```sql
-- migrate:up
CREATE TABLE conversations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    contact_id      UUID        NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    status          VARCHAR(20) NOT NULL DEFAULT 'open',
    channel         VARCHAR(20) NOT NULL,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT ck_conversations_status
        CHECK (status IN ('open', 'waiting', 'closed', 'archived')),
    CONSTRAINT ck_conversations_channel
        CHECK (channel IN ('whatsapp', 'instagram', 'facebook', 'webchat'))
);

-- FK indexes (organization_id, contact_id leftmost — não recria PK id)
CREATE INDEX ix_conversations_organization_id_updated_at
    ON conversations(organization_id, updated_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_conversations_contact_id
    ON conversations(contact_id)
    WHERE deleted_at IS NULL;

-- Partial GIN em metadata (containment queries)
CREATE INDEX ix_conversations_metadata_gin
    ON conversations USING GIN (metadata)
    WHERE deleted_at IS NULL;

-- migrate:down
DROP TABLE conversations;
```

## Don'ts (resumo)

- **NUNCA** `CREATE INDEX` em coluna PK (já existe).
- **NUNCA** FK sem índice — coluna FK precisa ser leftmost de algum índice.
- **NUNCA** GIN em JSONB consultado por extração (`->>`, `#>>`) — usa B-Tree de expressão.
- **NUNCA** `UNIQUE` em tabela com soft delete sem `WHERE deleted_at IS NULL`.
- **NUNCA** VARCHAR enum-like sem `CHECK` constraint (espelha o StrEnum/frozenset Python).
- **NUNCA** confie em naming auto-gerado pelo Postgres — use `ix_/ux_/uq_/ck_` explícito.
- **NUNCA** crie índice "por garantia" — só com WHERE quente justificando o write cost.
