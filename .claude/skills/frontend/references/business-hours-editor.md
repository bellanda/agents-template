# Editor de horário de funcionamento (agrupado)

Padrão da frota (decisão do usuário 2026-10-27): todo negócio repete o mesmo horário em vários dias
(Seg–Sex X, Sáb–Dom Y, resto fechado), então o editor define o horário UMA vez e o aplica a vários
dias — nunca 7 linhas independentes.

## Contrato de UX

- Cada **grupo** = chips de dia da semana (multi-seleção) + 1..N faixas (abre/fecha) + validação inline.
  Ex.: "Seg a Sex: 11:30–14:00 e 19:00–21:45", "Sáb e Dom: 12:00–15:00 e 19:00–21:45".
- Presets por grupo: **Seg–Sex**, **Fim de semana**, **Todos os dias**.
- Dia pertence a no máximo UM grupo: clicar o chip de um dia que está em outro grupo o MOVE; clicar o
  chip selecionado o fecha. Dia sem grupo = fechado (resumo "Fechado: Seg e Ter." abaixo dos grupos).
- Ajuste fino de um dia: criar grupo ("Adicionar outro horário") e marcar só aquele dia; "Copiar
  horário de…" (Select) preenche as faixas do grupo com as de outro dia.
- Adicionar/remover faixas por grupo (`maxSlots`, default 4; Kailos = 2). Sempre ≥1 faixa.
- Ao carregar, dias com faixas idênticas (ordem ignorada) viram um grupo sozinhos.
- Mensagens pt-BR: "O fechamento deve ser depois da abertura.", "Os horários deste grupo se
  sobrepõem.", "Preencha abertura e fechamento…", "Escolha ao menos um dia…".
- Mobile-first: cada grupo é `@container`, chips em `flex-wrap`, inputs `type="time"` (sem `text-sm`
  custom → não dispara zoom do iOS), zero `useIsMobile`, tokens semânticos shadcn.

## Regra de dado

O shape armazenado **NÃO muda**: um `{ closed, slots[] }` por dia da semana (`mon`..`sun`). Grupo é
só visão de UI, derivada por helpers puros. Horário já cadastrado é preservado: `groupHours` lê,
`ungroupHours` escreve (todas as 7 chaves; dia fora de grupo = `{closed:true, slots:[]}`). O editor
guarda `groups` em state local (grupo vazio/idêntico não some no meio da edição) e só re-deriva
quando o `value` muda de fora (`hoursEqual` — dia ausente == fechado, ordem das faixas ignorada).
Pai controlado precisa devolver o `value` emitido (como qualquer input controlado).

## Helpers puros (`references/business-hours-groups.ts`, copiar verbatim)

`groupHours`, `ungroupHours`, `hoursEqual`, `assignDays`, `toggleDayInGroup`, `addGroup`,
`closedDays`, `slotsFromDay`, `formatDayRange`, `validateSlots`, `validateGroups`,
`validateHoursMap` (para o pai bloquear "Salvar"), `WEEKDAYS`, `WEEKDAY_PRESETS`. Único ajuste por
app: o import de `BusinessHourSlot/BusinessHoursDay/WeekdayKey` (onde os tipos moram).

## Testes (por app)

1. Helpers: agrupa idênticos e faz round-trip; ausente/closed/sem slot = fechado e emite 7 chaves;
   sem aliasing de arrays; mover dia entre grupos e dropar grupo vazio; fechar dia; `addGroup`/
   `slotsFromDay`; `formatDayRange` (`Seg a Sex`, `Sáb e Dom`, `Seg, Qua e Sex`); validação
   (incompleto, invertido, igual, sobreposto, encostado OK).
2. Componente (harness controlado): grupos renderizados do dado salvo, mover dia emite o shape
   por dia, fechar dia, alerta pt-BR para faixa invertida.

## Implementação canônica

Emporion: `frontend/src/components/branding/{BusinessHoursEditor.tsx,business-hours-groups.ts}` +
`__tests__/`. Portado em Kailos (`components/organization-settings/`, com `maxSlots=2`,
`hoursEqual` no dirty e `validateHoursMap` no salvar). App novo com horário → copiar daqui.
Datas especiais/feriados são outro editor (emporion `SpecialDatesEditor`), fora deste padrão.
