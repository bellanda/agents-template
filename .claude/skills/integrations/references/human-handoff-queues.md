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
- **Trava de cumprimento (código, não prompt):** `handoff_to_human` de VENDA com o cliente tendo dito
  só "oi/opa/bom dia/tudo bem" na conversa é RECUSADO pela tool (`greeting_handoff_guard.is_greeting_only`
  sobre as inbound da conversa) e devolve ao modelo "não transferido: cumprimente e pergunte o que ele
  procura". Qualquer palavra fora do vocabulário de cumprimento, mídia ou botão libera. Pós-venda,
  trava de manipulação e transferências forçadas por código não passam pela trava. Origem: kailos
  2026-10-16, "opa" do dono virou lead porque o gatilho da equipe ("transfira sempre… rapidamente")
  venceu o método no Haiku `low` — regra só em prompt já tinha falhado duas vezes.

## Bloco de prompt em runtime

```
## EQUIPES DE ATENDIMENTO
Estas são as equipes humanas da loja. Os gatilhos dizem PARA QUAL equipe transferir; QUANDO
transferir segue o método (seção 8). Use `handoff_to_human` com o `queue_name` exato da equipe escolhida.

- `financiamento` — Financiamento: crédito, simulação, documentação do banco
  Assuntos desta equipe (escolhem a equipe, não a hora): pedir simulação, perguntar taxa, falar em entrada
```

Só filas **ativas** (`list_for_agent`, sem paginação: o consumidor é o prompt e uma loja tem uma
fila, talvez três) — mandar para fila desligada é o mesmo que não transferir. Ordem dos blocos de runtime: do estável ao
volátil (dados do negócio → filas → contexto atual com data/hora e "Loja agora"), que é o que o cache
de prompt aproveita.

## SLA e rodízio — "espera do cliente" (padrão desde 2026-10-23, kailos `services/queues/customer_wait/`)

O prazo conta **em segundos de expediente** (avaliador único de `business_hours`, fuso da loja). Mora
na API, não no cron. A varredura de 60 s do cron atrasava o aviso de 0 a 60 s e crescia com todas as
conversas abertas.

- **Quem conta:** só `human_handling` com a **janela de 24h da Meta aberta** (`last_inbound_at > now() − 24h`),
  em todos os passos. Janela fechada vai para o CRM, porque o vendedor só fala por template.
- **Dono que NUNCA respondeu** (rodízio / 1º contato): estourou o prazo da fila, passa ao próximo da
  escala (round-robin). Deu a volta inteira, volta ao primeiro, zera o ponteiro e grava `sla_escalated`
  uma vez por inbound. **Sem IA**: o cliente espera o 1º contato por definição, e um "ok, aguardo" logo
  após o handoff não pode matar o lead.
- **Dono que já respondeu** (lembrete): nunca é passado adiante (decisão 2026-10-09). A escada única
  dispara no prazo da fila, 20 min, 30 min, 1 h, 2 h, 4 h, 6 h e 8 h (`ladder.py`), sempre avisando o
  dono e a gestão. Depois de um downtime sai **um** aviso, o do maior passo vencido.
  - No passo em que há mensagem nova do cliente, a **IA responde só True/False**: "o cliente está
    esperando resposta?" (`ai_review.py`, `complete_structured`, `UsageContext`, teto de gasto).
  - True: avisa, e a escada segue sem perguntar de novo enquanto não houver movimento.
  - False: sem aviso, sem TV, sem rodízio. Grava `wait_dismissed_through` e um evento `ai_wait_dismissed`
    (chip na timeline), e a próxima mensagem do cliente abre uma espera nova, com relógio novo.
  - **Não existe timer de compromisso**: "vou fazer a simulação" seguido de "aguardo" é False.
  - Erro, timeout ou teto de gasto contam como True (fail-open).
- **Agenda por prazo:**
  - ZSET Valkey `customer_wait:due` (score = epoch do próximo passo), **só como despertador**.
  - Um ticker de 1 s no lifespan da API reivindica os vencidos (Lua + lease, seguro com N workers) e
    publica `queues.wait.check` (JetStream, `Nats-Msg-Id` = conversa:lease).
  - O consumer relê o Postgres sob trava por conversa e relê de novo depois da IA, antes de agir.
  - Ganchos: mensagem do cliente faz ZADD, resposta humana faz ZREM, transferência e handoff fazem ZADD.
  - Uma reconciliação de 5 min (um worker só) repõe o que faltar no ZSET.
- **Preparo 15 s antes do prazo:** veredito da IA e, onde há TV, clipe de voz. TV e celular saem no
  mesmo segundo, com a cor pelo nº do aviso (1º azul, 2º amarelo, 3º+ vermelho).
- Notificações `sla_reassigned`/`sla_escalated`/`sla_lead_owner_idle` (CHECK de `notifications.type`
  no mesmo PR). Toda mudança de dono publica o SSE `conversation.assigned` para o dono antigo, o novo e
  quem vê a caixa inteira; sem isso a conversa repassada só aparece no F5.
- **Mesma definição de espera em todo lugar:**
  - mensagem esperando = `created_at > GREATEST(last_outbound_at, wait_dismissed_through)`;
  - o relógio desconta `sla_owner_idle`/`ai_wait_dismissed` como troca de dono;
  - vale para o contador do inbox (`sla_deadline.py`, ver `frontend` → `whatsapp-inbox.md`), a tela
    "Quem está esperando" da TV e os ganchos. Mudou num lugar, muda nos outros.
- **Antes de ligar num app com volume:** rode um replay de alguns dias de prod pela regra nova e pelo
  prompt real (só leitura, export local, PII apagado). No kailos foram 5 dias: 90 perguntas, US$ 0,02,
  18 esperas caladas, todas corretas.

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
- **Rodízio por prazo** (desde 2026-10-23 em `customer_wait/rotation.py` + `decision.py`; antes
  `cron/sla_redistribution.py`, `5741fec`): o prazo de cada dono conta da CHEGADA da conversa nele
  (`sla_started_at` = último inbound ou a última troca de dono depois dele). Contar sempre do inbound
  fazia o recém-atribuído herdar um prazo já estourado: três vendedores em três minutos em prod.
- **Contador na UI** (`4e024cc`): `services/portals/whatsapp/sla_deadline.py` PREVÊ o próximo rodízio
  com as mesmas regras do avaliador. Dono que já respondeu, ou depois de `sla_escalated`, fica sem
  contador. `tests/whatsapp/test_sla_deadline.py` prende os dois.

## Assinatura do atendente humano (decisão do usuário 2026-10-16)

IA e todos os vendedores falam pelo MESMO número: depois da transferência o cliente só sabe quem
está do outro lado se a mensagem disser. Toda mensagem humana de texto livre (texto, link,
legenda de mídia) sai como `*PrimeiroNome*: texto` — primeiro nome de `users.name` (split, `*`
removido, capitalizado). Só no fio (o que vai à Meta); `text_body` salvo fica CRU (o inbox mostra
o autor e o histórico que a IA relê não ganha ruído). Não assinam: IA (persona própria) e template
(texto aprovado é fixo). Canônico: kailos `services/portals/whatsapp/human_signature.py`
(`fetch_human_sender_name` + `sign_human_text`) chamado em `whatsapp_service.send_message` /
`send_prepared_media(sender_name=)`; teste `TestHumanSignature`.

## Retomada quando o cliente some (decisão do usuário 2026-10-16)

Dois lados, MESMA função pura de agenda (`agent_followup_schedule.next_step_due_at`/`plan_followup`,
relógio injetado, sem I/O):

| Quem falou por último | Quem age | Etapas (após a última msg real) |
| --- | --- | --- |
| IA (`ai_handling`) | IA escreve ao cliente | 20 min após `read` (retoma o assunto + responde o que ficou pendente) · 3 h (ENTREGA algo: até 2 itens que cabem no que o cliente disse + 1 diferencial da config + pergunta de escolha) · 22 h ("peak-end": melhor opção + condição da loja + convite, nunca só "estamos à disposição") |
| Vendedor (`human_handling` + atribuído) | NOTIFICA o vendedor (sino + push), nunca o cliente | 1 h · 6 h · 21 h ("a janela fecha em 3h — depois só template") |

Invariantes (o bug clássico deste recurso é timer órfão / loop):
- **Sem timer agendado.** Um tick (cron → NATS → consumer, 60 s) DERIVA tudo das mensagens: âncora =
  última mensagem real; progresso = follow-ups (`metadata.followup_step`) / notificações
  (`data.step` + `anchor_at`) depois dela. Nada a cancelar.
- **Follow-up NUNCA move a âncora** (senão a IA manda um a cada 5 min para sempre).
- **Qualquer mensagem real reinicia** (cliente, IA respondendo, vendedor); handoff troca o lado;
  sair do estado para tudo. Reatribuição continua a sequência do vendedor no novo dono.
- **Horário comercial** da org (default 08–20 America/Sao_Paulo): fora dele adia para a abertura
  se a janela de 24h ainda tiver ≥30 min, senão pula. Gap mínimo de 1 h; uma etapa por passada.
- **Uma vez só:** trava de turno da conversa + claim `SET NX` no Valkey (conversa+etapa+âncora) +
  reconferência antes de enviar; cliente que escreve durante a geração descarta o follow-up.
- Texto da IA entra na memória da thread como `AIMessage` (`aupdate_state`), nunca como user falso.
- Máximo = nº de etapas; mais insistência derruba a nota de qualidade do número na Meta.
- Isso NÃO é o SLA/rodízio (cliente esperando + vendedor calado) — é o caso inverso.
- **A IA pode desistir (2026-10-16).** O prompt da retomada manda PRIMEIRO decidir se faz sentido
  escrever (cliente se despediu/recusou, a IA já se despediu, brincadeira/cantada, mensagem
  automática) e responder só `NAO_ENVIAR`; aí nada sai e um marcador no Valkey (25 h,
  `mark/is_agent_followup_declined`) encerra TODAS as etapas daquela conversa. Carro do estoque que
  não apareceu na conversa é sugestão nova — nunca "passei pra lembrar do X".
- **Follow-up que entrega valor (2026-10-30, kailos → emporion/nexarena):** "no follow up já entregar
  uns filés". As regras de neuromarketing da régua do Insights viram o bloco `_VALUE_PLAYBOOK` do
  prompt: dar antes de pedir, palavras do próprio cliente, número em vez de adjetivo, UM diferencial
  por mensagem, pergunta de escolha, escassez só se for fato e nunca como ameaça. **Todo fato da loja
  (diferencial, ressalva da garantia, quem negocia, horário) vem SÓ da configuração daquela loja**
  (o prompt do atendente ao qual a tarefa é anexada); nada de loja fica fixo no código. Limite por
  passo: 2 linhas no passo 1, 4 nos passos 2–3 (guard 3/5). Transcript junta rajada de fotos numa
  linha ("(14 fotos)"). Kailos: passos 2–3 veem o estoque inteiro e terminam com `FOTOS: <ids>`; o
  CÓDIGO filtra (estoque mostrado, com foto, ainda não visto na conversa via
  `metadata.photo_vehicle_id`, teto 2/1) e manda 1 foto de capa com legenda por carro, com
  `followup_step` (não move a âncora). Trailer em vez de `complete_structured`: tool forçada não
  convive com reasoning na Anthropic.

## Bom senso: quando a IA NÃO responde (decisão do usuário 2026-10-16)

"Deveria se portar como AI/Claude e se portou como chatbot robótico": a IA respondeu duas vezes a um
"72674 é seu código do Instagram" e seguiu vendendo a quem já tinha se despedido depois de cantadas.
- **Guard barato em código** (`automated_message_guard.py`): turno cujas mensagens novas são TODAS
  notificação automática (código 4–8 dígitos E frase "não compartilhe/é seu código/verification
  code") não chama o modelo. Os dois sinais juntos — "o código do anúncio é 12345" segue respondido.
- **O resto é julgamento do modelo:** seção "Quando NÃO responder" no prompt do atendente
  (automática; conversa encerrada com despedida dos dois lados; provocação repetida sem interesse;
  "na dúvida, responda"). O modelo responde só `SEM_RESPOSTA` (`AGENT_SILENCE_TOKEN`,
  `is_agent_silence` tolera aspas/ponto) e o dispatcher não envia nada.
- Nos dois casos o marcador de leitura (`last_agent_trigger_at`) avança, senão a próxima mensagem
  real é respondida junto com o OTP. Sem mensagem da IA, a retomada também não tem âncora.
- **Texto mal escrito é normal** (analfabetismo funcional é comum no Brasil — usuário, 2026-10-16):
  o prompt de todo atendente manda ler pelo som e pelo contexto ("ronda civi" = Honda Civic,
  "voagem" = Voyage), nunca corrigir nem pedir para escrever direito, e confirmar em uma frase só
  quando a leitura muda o pedido. Número que pode ser modelo ("1.30" = i30, "hb 20", "208") é
  buscado como modelo antes de virar motor/preço (Luziel: "carro 1.30" virou lista de R$ 130 mil).
- **Áudio de voz < 1,5 s** gravado no inbox não é enviado (toque sem querer chegou como áudio de
  0,22 s ao cliente): `MIN_VOICE_NOTE_MS` + `isVoiceNoteTooShort` em `useVoiceRecorder`, toast pt-BR.

Canônico: kailos `services/portals/whatsapp/{agent_followup*,seller_reengage}.py`.

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
- **NUNCA** varredura periódica de todas as conversas para disparar prazo: use a agenda por prazo (ZSET despertador + releitura do Postgres).
- **NUNCA** IA decidindo o 1º contato/rodízio do dono que nunca respondeu, nem silenciando por erro (fail-open = avisa).
- **NUNCA** escadas diferentes para TV e celular — mesmo passo, mesmo instante.
- **NUNCA** "fila" em texto visível — é "equipe" (a palavra técnica fica no código).
