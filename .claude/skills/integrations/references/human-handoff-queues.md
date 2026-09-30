# Equipes (filas humanas) e handoff do agente de IA

> Reference do gate `integrations`. Contrato de "a IA passa o cliente para uma pessoa" em projeto
> com atendente de IA no WhatsApp. Tela de instruções do agente → gate `frontend`
> (`agent-instructions.md`); política de disclosure/janela → `meta-policy.md`.

**Nome na tela = "Equipes"; no código = `queue`.** Todo texto que o usuário (ou o cliente, via
IA) lê diz equipe — menu, títulos, toasts, notificações, rótulos de permissão, bloco do prompt.
Tabelas, rotas, permissões (`queue:*`) e identificadores seguem `queue`: "fila" para o lojista soa
como fila de espera, e renomear o schema não compra nada (decisão de 2026-09-28).

A fila é a **unidade operacional completa**: quem atende (membros), o que ela atende, o que faz a IA
mandar o cliente para lá, e em quanto tempo alguém tem que responder. Tudo isso mora NA FILA — não
no Markdown do agente, não em `settings` da org.

## Schema

```sql
CREATE TABLE queues (
  id UUID PRIMARY KEY DEFAULT uuidv7(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name VARCHAR(64) NOT NULL,              -- técnico, é o que a tool recebe
  display_name VARCHAR(128) NOT NULL,
  description TEXT NOT NULL DEFAULT '',   -- "O que esta fila atende"
  handoff_triggers TEXT NOT NULL DEFAULT '', -- "Quando a IA transfere para cá"
  sla_response_seconds INTEGER NOT NULL DEFAULT 600,
  is_active BOOLEAN NOT NULL DEFAULT true,
  rotation_pointer INTEGER NOT NULL DEFAULT 0,  -- rodízio
  …,
  CONSTRAINT ck_queues_sla_response_seconds CHECK (sla_response_seconds BETWEEN 60 AND 86400)
);
-- + queue_members (queue_id, user_id, position, is_active)

ALTER TABLE <conversas> ADD COLUMN assigned_queue_id UUID REFERENCES queues(id) ON DELETE SET NULL;
CREATE INDEX ix_<conversas>_assigned_queue_id ON <conversas>(assigned_queue_id)
  WHERE assigned_queue_id IS NOT NULL;
```

- `description`/`handoff_triggers` são **TEXT**: entram inteiros no system prompt; `VARCHAR(n)` seria
  um teto arbitrário no meio do prompt.
- Prazo **por fila**, não por org: financiamento e vendas têm prazos diferentes. `60..86400` — um `0`
  digitado faria o cron reatribuir todo lead a cada passada.
- Conversa aponta a fila por **FK**, nunca pelo nome em texto (renomear a fila órfã as conversas). O
  inbox mostra o nome por `LEFT JOIN queues`. Backfill de FK desliga o trigger de `updated_at` —
  migração não é edição humana e não pode reordenar o inbox.

## Tool do agente

```python
@tool
async def handoff_to_human(queue_name: str, reason: str, summary: str, config: RunnableConfig) -> str:
```

- `queue_name` = o `name` exato de uma fila listada no prompt. **Nome desconhecido cai na fila
  principal** (`pick_routing_queue_id(preferred_name=…)`) em vez de falhar — recusar deixava o cliente
  falando com o robô.
- Numa transação: escolhe o atendente (rodízio, com afinidade por contato), grava `summary` como
  briefing, transiciona a conversa para `human_handling` com `assigned_user_id` + `assigned_queue_id`,
  e registra o evento de estado com `reason`. Depois publica o realtime para o atendente e para quem
  vê a caixa inteira — nunca broadcast para a org toda.
- A docstring da tool é **genérica**: a lista de filas é dinâmica e chega pelo prompt.

## Bloco de prompt em runtime

```
## EQUIPES DE ATENDIMENTO
Estas são as equipes humanas da loja. Use a tool `handoff_to_human` com o `queue_name` exato
quando o assunto do cliente casar com os gatilhos de uma delas.

- `financiamento` — Financiamento: crédito, simulação, documentação do banco
  Transferir quando: pedir simulação, perguntar taxa, falar em entrada
```

Só filas **ativas** (`list_for_agent`, sem paginação: o consumidor é o prompt e uma loja tem uma
fila, talvez três) — mandar para fila desligada é o mesmo que não transferir. Ordem dos blocos de runtime: do estável ao
volátil (dados do negócio → filas → contexto atual com data/hora e "Loja agora"), que é o que o cache
de prompt aproveita.

## SLA e rodízio

- Cron conta o prazo **em segundos de expediente** (avaliador único de `business_hours`, fuso da loja).
- Estourou → próximo da escala (round-robin); deu a volta inteira sem resposta → volta ao primeiro,
  zera o ponteiro, grava `sla_escalated` **uma vez por inbound** e avisa a gestão.
- O cron publica no JetStream (`CRON_JOBS`, declarado igual nos dois lados); o consumer da API cria as
  notificações `sla_reassigned`/`sla_escalated` (CHECK de `notifications.type` no mesmo PR) e o
  realtime — sem isso a conversa repassada só aparece no F5.

## API e permissões

- `queue:read` / `queue:manage` de verdade na rota (nunca check de papel).
- CRUD completo: listagem `PagedResponse`, GET, PATCH, DELETE com guarda **"última fila ativa"** (sem
  fila, o handoff não tem para onde ir); membros com 204.

## UI (hub de Configurações › Equipes)

- Um `FormDialog` único criar/editar: Nome técnico, Rótulo, **O que esta equipe atende**, **Quando a IA
  transfere para cá**, prazo em `NumericField` ("Responder em até", segundos, passo 60, mesma faixa do CHECK; o hint diz que o relógio corre só no horário comercial).
- Exclusão por `ConfirmDialog`; membros por picker com busca.

## Don'ts

- **NUNCA** gatilho de transferência no Markdown do agente — é `handoff_triggers` da fila.
- **NUNCA** `assigned_queue` como texto na conversa.
- **NUNCA** tool que falha com nome de fila desconhecido.
- **NUNCA** SLA em segundos corridos — expediente da loja.
- **NUNCA** "fila" em texto visível — é "equipe" (a palavra técnica fica no código).
