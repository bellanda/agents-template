# Charts — `ChartContainer` + `ChartConfig` + `ChartTooltip`

Shadcn Charts é um **wrapper sobre Recharts** disponível no registry oficial (`bunx shadcn@latest add chart`). Não é uma lib de gráficos nova — é um conjunto de componentes que dá theming consistente (semantic colors via CSS vars), tooltip uniforme, e legend estilo shadcn.

## Stack

| Camada              | O que é                                                               |
| ------------------- | --------------------------------------------------------------------- |
| Renderização        | **Recharts** (SVG, declarativo, React-native)                         |
| Wrapper Shadcn      | `<ChartContainer>`, `<ChartTooltip>`, `<ChartTooltipContent>`, `<ChartLegend>`, `<ChartLegendContent>` |
| Theming             | `ChartConfig` mapeando dataKey → `{ label, color: "var(--chart-N)" }` |
| Cores               | CSS vars `--chart-1` a `--chart-5` em `index.css > @theme`            |

## Pattern canônico

```tsx
import { Bar, BarChart, CartesianGrid, XAxis } from "recharts";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";

const chartData = [
  { month: "Jan", revenue: 186 },
  { month: "Feb", revenue: 305 },
  /* ... */
];

const chartConfig = {
  revenue: {
    label: "Receita",
    color: "var(--chart-1)",
  },
} satisfies ChartConfig;

export function RevenueChart() {
  return (
    <ChartContainer config={chartConfig} className="min-h-[200px] w-full">
      <BarChart accessibilityLayer data={chartData}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="month" tickLine={false} tickMargin={10} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Bar dataKey="revenue" fill="var(--color-revenue)" radius={4} />
      </BarChart>
    </ChartContainer>
  );
}
```

Notar:

- `var(--color-revenue)` é **gerado automaticamente** pelo `ChartContainer` a partir do `config.revenue.color`. Não escrever `fill="oklch(...)"` direto no `<Bar>`.
- `accessibilityLayer` no Recharts root — sempre.
- `min-h-[200px] w-full` no `ChartContainer` — Recharts precisa de altura definida ou colapsa para 0.

## Semantic colors

```css
/* index.css */
@theme inline {
  --chart-1: oklch(0.646 0.222 41.116);
  --chart-2: oklch(0.6 0.118 184.704);
  --chart-3: oklch(0.398 0.07 227.392);
  --chart-4: oklch(0.828 0.189 84.429);
  --chart-5: oklch(0.769 0.188 70.08);
}
```

5 cores semânticas + variantes dark mode automatizadas por shadcn. **NUNCA** raw color em chart (`fill="#3b82f6"`, `fill="oklch(...)"` inline).

## Tipos de chart cobertos

Registry oferece exemplos para todos os tipos comuns (`bunx shadcn@latest add chart-bar`, `chart-line`, `chart-area`, `chart-pie`, `chart-radar`, `chart-radial`). Use o que casa com o dado:

| Dado                                     | Chart                                    |
| ---------------------------------------- | ---------------------------------------- |
| Comparação categórica (vendas por região)| Bar (vertical) ou Horizontal Bar         |
| Evolução temporal (1 série)              | Line ou Area                             |
| Evolução temporal (N séries)             | Line multi-série ou Area stacked         |
| Proporção (poucas categorias, < 6)       | Pie ou Donut                             |
| Distribuição em múltiplas dimensões      | Radar                                    |
| Único valor com referência               | Radial                                   |
| Distribuição numérica                    | Histogram (Bar sobre buckets)            |

Para escolha de chart por tipo de dado, ver skill `data-visualization` (também fala de matplotlib mas o reasoning de qual chart usar é stack-agnostic).

## Performance — ResizeObserver leak (CRÍTICO)

Recharts internamente usa `<ResponsiveContainer>` que registra um **`ResizeObserver`**. Se o chart re-monta a cada render do parent (props instáveis, parent não memoizado, key mudando), o observer vaza — e o `mount/unmount` desbalanceia.

Sintoma: app degrada após N minutos, memória cresce, CPU alta idle. Ver skill `frontend-performance-ultimate` para diagnóstico completo.

### Checklist por chart wrappado

- ✅ **`React.memo`** no wrapper do chart.
- ✅ **`useMemo`** no objeto `data` passado pro chart (não criar inline).
- ✅ **`useMemo` ou constante de módulo** no `ChartConfig`.
- ✅ **`useCallback`** em qualquer handler passado (`onClick` do bar, etc.).
- ✅ Em rotas com polling (TanStack Query `refetchInterval`), garantir que o **polling não vive no route component** — leaf memoizado dono da query (ver `frontend-performance-ultimate > Polling isolation`).
- ✅ **`key` estável** se renderizar lista de charts. ID do dataset, NUNCA index.

```tsx
// ❌ ANTES — chart re-mount em todo render
function Dashboard() {
  const { data } = useQuery({ queryKey: ["revenue"], queryFn });
  return (
    <ChartContainer
      config={{ revenue: { label: "Receita", color: "var(--chart-1)" } }}
      data={(data ?? []).map((d) => ({ month: d.m, revenue: d.r }))}
    >
      {/* ... */}
    </ChartContainer>
  );
}

// ✅ DEPOIS — wrapper memoizado, data estável, config estável
const CHART_CONFIG = {
  revenue: { label: "Receita", color: "var(--chart-1)" },
} satisfies ChartConfig;

const RevenueChart = memo(function RevenueChart({
  rows,
}: {
  rows: Array<{ month: string; revenue: number }>;
}) {
  return (
    <ChartContainer config={CHART_CONFIG} className="min-h-[200px] w-full">
      <BarChart accessibilityLayer data={rows}>
        {/* ... */}
      </BarChart>
    </ChartContainer>
  );
});

function Dashboard() {
  const { data } = useQuery({ queryKey: ["revenue"], queryFn });
  const rows = useMemo(
    () => (data ?? []).map((d) => ({ month: d.m, revenue: d.r })),
    [data],
  );
  return <RevenueChart rows={rows} />;
}
```

## Tooltip e Legend

```tsx
<ChartTooltip content={<ChartTooltipContent hideLabel />} />
<ChartLegend content={<ChartLegendContent />} />
```

`hideLabel` quando só faz sentido o valor (pie chart de 1 série). `nameKey` para customizar qual campo aparece no tooltip.

## Quando NÃO usar Shadcn Charts

- Chart 3D, scatter complexo, gráfico de rede → Recharts não cobre. Considerar `nivo`, `visx`, ou D3 direto.
- Tabela de dados disfarçada de chart (heatmap de 50×50) → renderize tabela com cores semantic.
- Sparkline minúsculo em row de tabela → Recharts é overkill. Usar SVG inline manual ou lib leve.

## Resumo

1. `bunx shadcn@latest add chart` + variante específica (`chart-bar`, `chart-line`...).
2. `ChartConfig` em const fora do componente OU `useMemo`.
3. Wrapper `memo` + `data` em `useMemo` + handlers em `useCallback`.
4. Cores via `var(--chart-N)` no config, NUNCA inline.
5. Em página com polling, leaf isolado tem a query — não o route component.
