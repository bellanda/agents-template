# Transitions — `useTransition` / `startTransition`

## Quando usar

Quando uma mudança de state dispara render pesado (filtrar 10k linhas, trocar tab com chart, mudar período em dashboard) e o input fica congelado enquanto o React renderiza.

`useTransition` marca o update como **não-urgente**. React continua respondendo a input do user, e processa a transição em background.

## Pattern canônico

```tsx
import { useState, useTransition } from "react";

export function VehicleFilter({ vehicles }: { vehicles: Vehicle[] }) {
  const [query, setQuery] = useState("");
  const [filtered, setFiltered] = useState(vehicles);
  const [isPending, startTransition] = useTransition();

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    setQuery(e.target.value); // urgent — input atualiza imediato
    startTransition(() => {
      // não-urgente — filtro pesado
      setFiltered(vehicles.filter((v) => v.plate.includes(e.target.value)));
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <Input value={query} onChange={handleChange} />
      <div className={isPending ? "opacity-50" : ""}>
        <VehicleList vehicles={filtered} />
      </div>
    </div>
  );
}
```

`query` atualiza instantâneo (input responde). `filtered` atualiza quando der. `isPending` mostra feedback de loading sem bloquear input.

## `startTransition` standalone

Sem precisar de `isPending`, importável direto:

```tsx
import { startTransition } from "react";

function handleTabChange(tab: string) {
  setActiveTab(tab); // urgent
  startTransition(() => {
    setChartData(loadChartFor(tab)); // pesado
  });
}
```

## Regras

- Use em **state updates client-side pesados** — filter, sort, map de grande lista, troca de chart, troca de tab com componente custoso.
- `startTransition` só aceita **state updates síncronos** dentro do callback (em React 19, também aceita async — útil pra Actions).
- `isPending` é por-transição (não global). Múltiplos `useTransition` em componentes diferentes não compartilham flag.
- Combinar com `useDeferredValue` quando o input vem de prop, não de event handler local.

## Quando NÃO usar

- Re-render rápido (< 16ms) — não precisa.
- Data fetching — use TanStack Query (já tem `isFetching`) ou `use()` + Suspense.
- Form submit async — use `useActionState` (que já roda em Action transition internamente).

## Combinação com `useOptimistic`

`useOptimistic` exige rodar dentro de Action ou `startTransition`. Pattern frequente: botão que faz mutação + UI optimistic + transição não-urgente para atualizar dados secundários.
