# Dashboard — KPI, período e gráficos (REFERENCE, não obrigatória)

> Reference do gate `frontend`. Abra quando for construir um dashboard **novo** e quiser partir de
> peças prontas. **Não é padrão obrigatório** (decisão de **2026-10-01**: dinheiro, período/KPI e
> histórico ficam por projeto — nenhum app existente é migrado para estas peças). Gráficos em si:
> skill `shadcn` → `rules/charts.md`.

## O que existe (kailos `frontend/src/`)

| Peça                         | Arquivo                                  | Para quê                                                              |
| ---------------------------- | ---------------------------------------- | --------------------------------------------------------------------- |
| `PeriodSelector`             | `components/dashboard/PeriodSelector.tsx` | `Select` de período + intervalo personalizado em `FormDialog`         |
| `StatCard`                   | `components/dashboard/StatCard.tsx`       | Card de KPI: rótulo, valor, delta vs período anterior, ícone          |
| `ui/chart.tsx`               | `components/ui/chart.tsx`                 | Wrapper shadcn de Recharts (`ChartContainer`, `ChartConfig`, tooltip) |
| Barra de filtros do dashboard | `components/dashboard/GlobalFiltersBar.tsx` | Controles no topo à esquerda, acima das abas (ver `list-screen.md`) |

### `PeriodSelector`

```tsx
<PeriodSelector
  value={period}                       // PeriodKey: "today" | "yesterday" | "wtd" | "mtd" | "ytd" | "last_year" | "all" | "custom" | …
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
- Grid de KPIs: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4` (peers → grid). Cada card é um
  `<Card data-kpi-card>`. O `StatCard` do kailos usa `p-5` no `CardContent`; num app novo siga o
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
