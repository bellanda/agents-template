# Equipes — grid de cards + editor one-page

> Reference do gate `frontend`. Abra ANTES de construir/alterar a tela de **Equipes** (filas humanas
> do atendente de IA: quem atende, o que atende, quando a IA transfere, SLA, rodízio). Contrato de
> backend, schema, tool `handoff_to_human` e rodízio → gate `integrations`
> (`references/human-handoff-queues.md`). Redesenho de **2026-10-01**; vale para kailos e emporion
> (os únicos apps com handoff para humano). **Canônico:** kailos
> `components/settings/sections/QueuesSection.tsx` (seção `queues` do hub — ver `settings-dialog.md`)
> + `sections/queues/`: `QueueCard.tsx` (card), `QueueEditorDialog.tsx` (FormDialog + rodapé +
> ConfirmDialog), `QueueDataFields.tsx` (coluna de dados), `QueueMembersPanel.tsx` (dnd-kit + adicionar),
> `queue-draft.ts` (`QueueDraft`, `toDraft`, `isSameDraft`, `queueKeyFromLabel`). Copie a pasta inteira.

**Nome na tela = "Equipes"; no código = `queue`.** Nada de "fila" em texto de usuário.

**Princípio:** a equipe é a unidade operacional completa e se edita **numa página só** — dados e
membros juntos, sem navegar lista → detalhe. O desenho tem o mesmo tom e a mesma estrutura do editor
do agente (`agent-instructions.md`): cards, um Salvar, um botão vermelho de excluir no rodapé.

## Anatomia

```
┌ Seção "Equipes" ────────────────────────────────────── [ + Nova equipe ] ┐
│ ┌ card ───────────┐ ┌ card ───────────┐ ┌ card ───────────┐            │   1 col (mobile)
│ │ Vendas          │ │ Financiamento   │ │ Pós-venda       │            │   2–3 cols (desktop)
│ │ 3 membros       │ │ 2 membros       │ │ 1 membro        │            │
│ │ Responder em 10 │ │ Responder em 1h │ │ …               │            │
│ │ min · 2 gatilhos│ │                 │ │                 │            │
│ └─────────────────┘ └─────────────────┘ └─────────────────┘            │
└───────────────────────────────────────────────────────────────────────────┘

Clique no card (ou "Nova equipe") → FormDialog size="xl" (full-bleed no mobile)
┌ Editar equipe ───────────────────────────────────────────────────── X ┐
│ DADOS (esquerda)                    │ MEMBROS E ORDEM (direita)        │   desktop: 2 colunas
│  Nome da equipe                     │  ≡ #1 Ana            [x]         │   mobile: empilhado
│  O que esta equipe atende           │  ≡ #2 Bruno          [x]         │   (dados → membros)
│  Quando a IA transfere para cá      │  [ + Adicionar membro ▾ ]        │
│  Responder em até (minutos)         │  texto do rodízio (emporion)      │
├─────────────────────────────────────────────────────────────────────────┤
│ [ Excluir equipe ]  (vermelho)                               [ Salvar ] │
└─────────────────────────────────────────────────────────────────────────┘
```

- **Lista = grid de cards**: `grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3`. O card é UM
  `<button>` inteiro (alvo ≥44px) que abre o editor; mostra **só** nome + resumo (nº de membros, SLA
  legível `10 min`/`1h`, nº/trecho de gatilhos). **Sem lápis, sem lixeira no card** — ação destrutiva
  mora dentro do editor. Vazio → `EmptyState` com o CTA "Nova equipe" (ver `feedback-states.md`).
- **"Nova equipe" abre o MESMO editor**, vazio. Um `FormDialog` só para os dois modos
  (`editing: Queue | "new" | null`), um `ConfirmDialog` só, controlado pelo item.
- **Editor = `FormDialog` `size="xl"`** (tem `<input>` → `DialogContent` cru é proibido, 8e). Corpo em
  `grid gap-8 lg:grid-cols-2`; **um scroll só** (o do corpo do `FormDialog`) — nada de scroll por
  coluna. Mobile = coluna única empilhada, dados primeiro.
- **Coluna esquerda (dados)**: nome, o que atende, gatilhos de handoff, SLA em minutos
  (`NumericField`, limites vindos do backend `SLA_RESPONSE_MIN/MAX_SECONDS`), e o texto de rodízio do
  emporion quando existir. A chave técnica (`name`) é gerada do nome (`queueKeyFromLabel`:
  "Pós-venda" → `pos_venda`) **só na criação** — o lojista nunca digita chave.
- **Coluna direita (membros + ordem)**: lista ordenável com **dnd-kit** (`DndContext` +
  `SortableContext` + `useSortable`; arrasta a **linha inteira** com `useRowDragSensors`
  (`lib/dnd/row-drag-sensors.ts`, kailos `f8f22940`: mouse com `distance: 6`, toque com long-press para
  não roubar a rolagem, + `KeyboardSensor`); o `≡` fica como afordância com `aria-label`), badge `#n`, remover `X`, e "Adicionar membro" (Popover + Command
  sobre os membros da org que ainda não estão na equipe). Texto de apoio: "O primeiro da lista
  recebe o próximo cliente que a IA passar, depois o segundo — um de cada vez."
- **Rodapé** (slot `footer` do `FormDialog`): **"Excluir equipe"** vermelho (`variant="destructive"`,
  só em edição, à esquerda) → `ConfirmDialog` (`destructive`, `busy`) · **Salvar** à direita. Um
  Salvar grava dados **e** membros/ordem (duas mutations em sequência, um toast, erro único) — o
  usuário não vê "salvar dados" separado de "salvar ordem".
- Rascunho local (`QueueDraft` + `orderedMembers`) é descartado ao fechar sem salvar; **salvar nova
  ordem zera o ponteiro do rodízio** (avise no texto de apoio).

## Invariantes

- Cada equipe tem prazo próprio (SLA por equipe, não por org); `sla_response_seconds` 60..86400.
- Gate de permissão = `queue:manage` (seção some do hub sem ela; `isAdminLevel` só no OR do bypass).
- Dialog-em-Dialog: o editor abre POR CIMA do hub de settings (hub→ação efêmera, permitido); o
  `ConfirmDialog` de excluir abre por cima do editor — idem.
- Texto que o usuário lê é "equipe"; identificadores seguem `queue`.
- Equipe removida: conversas em andamento ficam com o vendedor atual, **sem equipe** — diga isso no
  `ConfirmDialog`.

## Ausência do membro (kailos + emporion, 2026-11-16)

Regra de negócio e backend → skill `integrations` › `human-handoff-queues.md` §"Ausência do vendedor".

- Linha de membro no editor: chip "Ausente até 23/11 18:00" / "Ausente (sem data)" / "Ausência a partir
  de 20/11" + botão **"Ausência"** (só ícone no celular, alvo ≥36px; o grid de membros leva
  `[&>*]:min-w-0` para não vazar a 390px). "Próximo a receber" pula quem está ausente AGORA (agendada
  ainda conta). Card da equipe mostra "{n} ausente(s)" (`absent_member_count`).
- **`MemberAbsenceDialog`** (`FormDialog` `size="lg"`, abre por cima do editor), pastas
  `components/settings/sections/queues/absence/`: Motivo (Pausa curta · Folga · Férias / viagem · Sem
  novos leads (advertência) · Outro) → Início (Agora / Agendar) → Até (1 hora · 3 horas · Fim do dia ·
  1 · 3 · 7 dias · data · Sem data), padrão do "Até" segue o motivo (pausa 3 h, folga 1 dia, férias e
  advertência 7 dias, outro sem data) até o gestor mexer → conversas atuais (manter /
  transferir para… `MemberPicker excludeUserIds` / distribuir na equipe; escondido se agendada) →
  "se o cliente responder" (só ao manter) → observação. Datas no dia LOCAL; payload em UTC ISO.
- Ausência existente: resumo + "Transferir conversas agora" + **"Encerrar ausência"** (botão normal,
  NÃO destrutivo — só devolve a pessoa ao rodízio) + "Alterar ausência" (nova substitui).
- Tempo real: o backend anuncia `entity.changed` da equipe (kailos `"queue"`, emporion `"queues"`) →
  `entity-handlers.ts` invalida a entidade `queue` (que é dona do path `member-absences`).
- kailos: tirar alguém da ÚLTIMA equipe com conversas/atendimentos abertos pede `ConfirmDialog` antes
  de Salvar ("vão para os outros da equipe — para só pausar, use Ausência"); o próprio vendedor vê
  "Você está sem receber novos leads até …" (`MyAbsenceNotice`).

## Anti-padrões

- **NUNCA** lista em `<ul>` com lápis + lixeira por linha, nem tela de detalhe separada (`QueueDetailView`
  era a versão antiga: lista → detalhe → "Salvar ordem" separado de "Salvar").
- **NUNCA** botão Excluir fora do rodapé do editor, nem confirmação inline.
- **NUNCA** `DialogContent` cru no editor; **NUNCA** scroll aninhado por coluna.
- **NUNCA** pedir ao lojista a chave técnica da equipe.
- **NUNCA** gatilhos/horário/estoque no Markdown do agente — gatilhos moram NA equipe (fonte única).
