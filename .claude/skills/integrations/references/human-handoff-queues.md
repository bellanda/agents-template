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
  realtime — sem isso a conversa repassada só aparece no F5. **Toda** mudança de dono feita pelo
  cron (rodízio, volta ao primeiro) publica o SSE `conversation.assigned` para o dono antigo, o novo e
  quem vê a caixa inteira (kailos `cron_events_consumer.py`, 2026-10-09).
- O inbox mostra o contador até o próximo rodízio (`sla_deadline_at`/`sla_paused_until`, ver
  `frontend` → `whatsapp-inbox.md`); o cálculo espelha o cron — mudou a regra num, muda no outro.

## Para quem vai o handoff (kailos, 2026-10-09)

Ordem: vendedor que o cliente citou (`seller_id`, achado por `find_seller` com fuzzy) → quem vendeu
(só `kind="post_sale"`, específico do kailos) → atendente de sempre (`contacts.preferred_user_id`) →
rodízio. Inativo/fora da equipe cai para o próximo degrau. O motivo vai em `routing` no metadata do
evento e aparece no `EventCard`. As equipes dizem PARA QUEM; QUANDO transferir é do método da
plataforma (prompt-base), não do gatilho da equipe.

### Rodízio e fila de roteamento (kailos `services/queues/`)

- **`assignment.pick_assignee(conn, org_id, contact_id=…)`** é o ÚNICO ponto que decide dono quando não há
  vendedor explícito (handoff da IA, anti-abuso/contato bloqueado). Chame dentro de transação:
  `queue_repository.pick_routing_queue_id` escolhe a fila (ativa **com membro ativo**, preferindo a de
  vendas criada com a org) e `pick_next_for_contact` respeita o vendedor grudado no contato e senão avança
  o `rotation_pointer` sob `FOR UPDATE` (dois handoffs simultâneos não pegam o mesmo). Sem fila utilizável
  cai no titular da loja (`organizations.owner_user_id`, senão o admin mais antigo): conversa nunca fica
  órfã. Antes só o `owner` recebia contato bloqueado (SQL cru + 403 de `assigned_user_id`), o que numa loja
  de dez vendedores era uma fila de um.
- **`handoff_routing.py`** monta `HandoffAssignment(user_id, routing, seller_name)` na ordem
  `explicit_seller` → `sold_by` (só `kind="post_sale"`) → `preferred` → `rotation`; `find_seller` casa nome
  por substring/palavra e só então fuzzy (`SELLER_NAME_FUZZY_THRESHOLD = 85`, rapidfuzz); abaixo disso a IA
  pergunta de novo em vez de transferir para a pessoa errada.
- **`queue_repository.list_serving_members`** = critério único de "vendedor válido": usuário ativo + membro
  da org + membro ATIVO de ao menos uma fila ATIVA. Alimenta `find_seller` e a checagem do `seller_id`;
  vendedor desligado ou fora das filas nunca recebe cliente por indicação da IA (cai no próximo degrau).
- **Contato bloqueado pelo anti-abuso** (`abuse_service.apply_abuse`): em UMA transação bloqueia
  (`contacts.is_blocked` + `block_reason`), grava auditoria `CONTACT_BLOCKED` (bloqueio automático erra —
  cliente que manda 25 fotos do carro que vende parece robô), escolhe dono por `pick_assignee`, transiciona
  para `human_handling` (evento `abuse_<motivo>`), deixa nota interna com o motivo e notifica o dono. O
  agente NÃO é acionado. Desbloqueio é ação humana (`whatsapp:manage`) → `whatsapp-inbox.md`.
- **Rodízio por prazo** (`cron/sla_redistribution.py`, commit `5741fec`, 2026-10-09): o prazo de cada dono
  conta da CHEGADA da conversa nele (`sla_started_at` = último inbound ou última mudança de dono depois
  dele). Contar sempre do inbound fazia o recém-atribuído herdar prazo já estourado: três vendedores em
  três minutos em prod. O rodízio NUNCA passa adiante quem já respondeu na conversa (decisão do usuário
  2026-10-09): estourou o prazo → grava `sla_owner_idle` + evento `cron.lead.owner_idle` para a gestão,
  uma vez por inbound. Piso da varredura 1 min (mínimo da fila). Mudança de dono pelo cron publica
  `conversation.assigned` (SSE) — sem F5.
- **Contador e motivo na UI** (`4e024cc`, 2026-10-09): `services/portals/whatsapp/sla_deadline.py` PREVÊ o
  próximo rodízio espelhando as regras do cron (só `human_handling` com inbound sem resposta; dono que já
  respondeu = sem contador; relógio recomeça a cada troca de dono; após a volta inteira `sla_escalated` =
  sem contador). Muda o cron, muda o arquivo — `tests/whatsapp/test_sla_deadline.py` prende os dois.

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
