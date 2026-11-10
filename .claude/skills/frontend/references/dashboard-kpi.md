# Dashboard — KPI, período e gráficos (REFERENCE, não obrigatória)

> Reference do gate `frontend`. Abra quando for construir um dashboard **novo** e quiser partir de
> peças prontas. KPI, dinheiro e histórico ficam por projeto (decisão de **2026-10-01**). **O filtro
> de data é a exceção: é padrão da frota** (decisão do usuário **2026-11-09**, seção abaixo).
> Gráficos em si: skill `shadcn` → `rules/charts.md`.

## Filtro central de data (padrão da frota, 2026-11-09)

"Outros filtros são pontuais de cada tela e app, mas o filtro de data tem que ser padrão de todos."
Toda tela com recorte por período usa estas linhas, nesta ordem:

Hoje · Ontem · **Dia recente** · Semana · **Semana passada** · Mês · **Mês passado** · Ano · Ano
passado · Todos os tempos · Personalizado…

- App pode **manter** janelas próprias depois delas (Últimos 7 dias, 90 dias, 12 meses) e **omitir**
  só o que o backend dele não aceita (limite de janela do emporion, histórico curto do akmeo).
- **Semana passada** = segunda a domingo fechados, comparada com a semana anterior. **Mês passado** =
  dia 1 ao último dia, comparado com o mês INTEIRO anterior (nunca "mesmo tamanho para trás": março
  contra fevereiro erraria o início). Meta de período fechado mede como a do período corrente.
- **Dia recente** é uma linha normal da lista. Abre `RecentDayDialog`: UMA grade com os últimos 30
  dias corridos (`recent-day.ts`), atravessando o mês, segunda na 1ª coluna, hoje por último e já
  marcado. Clicar aplica e fecha, sem botão Aplicar e sem navegar mês; dia mais antigo é
  "Personalizado…". Não existe chave de backend: o dia viaja como período personalizado de início =
  fim, e a comparação é o dia anterior. O gatilho mostra "sex., 06/11".
  App sem período personalizado (akmeo, lista fechada com uma string só) manda `day:YYYY-MM-DD`
  nessa mesma string, e dia futuro vale como hoje.
- Sem dependência nova: a grade é `Button` em `grid-cols-7`, não precisa de `react-day-picker`.
- Dia é sempre dia local (`toLocalDateKey`/`addDaysToDateKey`); chaves comparam como string.
- Canônicos: `references/recent-day.ts` e `references/recent-day-dialog.tsx`.

## O que existe (kailos `frontend/src/`)

| Peça                         | Arquivo                                  | Para quê                                                              |
| ---------------------------- | ---------------------------------------- | --------------------------------------------------------------------- |
| `PeriodSelector`             | `components/dashboard/PeriodSelector.tsx` | `Select` de período + intervalo personalizado em `FormDialog`         |
| `RecentDayDialog`            | `components/dashboard/RecentDayDialog.tsx` | Calendário de um dia dos últimos 30 (linha "Dia recente")             |
| `StatCard`                   | `components/dashboard/StatCard.tsx`       | Card de KPI: rótulo, valor, delta vs período anterior, ícone          |
| `ui/chart.tsx`               | `components/ui/chart.tsx`                 | Wrapper shadcn de Recharts (`ChartContainer`, `ChartConfig`, tooltip) |
| Barra de filtros do dashboard | `components/dashboard/GlobalFiltersBar.tsx` | Controles no topo à esquerda, acima das abas (ver `list-screen.md`) |

### `PeriodSelector`

```tsx
<PeriodSelector
  value={period}                       // PeriodKey: "today" | "yesterday" | "wtd" | "last_week" | "mtd" | "last_month" | "ytd" | "last_year" | "all" | "custom" | …
  start={start} end={end}              // ISO date, só com "custom"
  onChange={({ period, start, end }) => navigate({ search: (p) => ({ ...p, period, start, end }) })}
  variant="default"                    // "title" = trigger sem borda no tamanho do título da página
/>
```

- Período e datas moram **na URL** (`validateSearch`), nunca em `useState`.
- "Personalizado…" abre `FormDialog` `size="sm"` com `De`/`Até` (`<Input type="date">`), validação
  `fim ≥ início` e janela máx. **365 dias**; fechar sem aplicar **descarta** o rascunho (reset no
  `onOpenChange`, já que não há botão Cancelar).
- Rótulos pt-BR vêm de `periodLabel()` (`lib/utils/dates.ts`); o backend devolve a janela resolvida
  (`PeriodWindowInfo`: `start/end/prevStart/prevEnd`) — o front **não** calcula janela de
  comparação.
- No celular a barra de filtros vira botão "Filtros" → `FormDialog` (troca por CSS, nunca `useIsMobile()`).

### `StatCard`

```tsx
<StatCard
  label="Leads" metric={overview.leads}        // { current, previous, deltaAbs, deltaPct } | null
  format={formatBRL}                            // formatBRL | formatPercent | formatDecimal | default pt-BR
  icon={<LuUsers className="size-5" />} hideDelta={false}
/>
```

- `null`/ausente renderiza `—` (nunca `0` falso). Delta: verde ↑ / vermelho ↓ / neutro `—`, com
  "vs período anterior"; cores `emerald/rose` com variante `dark:` (exceção sancionada: semântica de
  tendência, não tema).
- Grid de KPIs: `grid-cols-[repeat(auto-fill,minmax(12rem,1fr))]` (ou `grid-cols-1
  @xl/main:grid-cols-2 @4xl/main:grid-cols-4`) — largura útil, não viewport. Cada card é um
  `<Card data-kpi-card className="@container">` e o valor é `tabular-nums whitespace-nowrap` com
  tamanho por container (`text-xl @[12rem]:text-2xl @[16rem]:text-3xl`), nunca cortado. O `StatCard` do kailos usa `p-5` no `CardContent`; num app novo siga o
  `Card` v4 (`shadcn-v4-primitives.md`: compacto = `gap-4 py-4` + slots `px-4`).

## Fora do padrão — por projeto

- **Campo de dinheiro** (máscara BRL, centavos vs reais, `NumericField`/`money-mask.ts`/
  `lib/utils/currency.ts`): cada app tem o seu; não unifique.
- **Histórico/linha do tempo** de entidade (`VehicleHistoryTimeline`, `audit-timeline`,
  `ui/timeline`): cada app modela o seu evento. O `EventCard` do inbox (`whatsapp-inbox.md`) **não** é
  uma timeline.

## Regras que valem mesmo sendo reference

- Cores de série via `ChartConfig` + vars `--chart-*` (nunca hex cru); tooltip em pt-BR.
- Gráfico monta/desmonta limpo (`LazyMount` para os fora da dobra) — budget de render em
  `performance-preventivo.md`.
- Número formatado por `Intl` pt-BR (`formatBRL`, `toLocaleString("pt-BR")`), nunca `toFixed` solto.
