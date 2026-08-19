# Performance — Checklist Preventivo

> Reference do gate `frontend` (item 6 do checklist). Rode esta lista sempre que tocar em context
> provider, polling hook, store custom ou rota com muitos charts. Se algum item falhar, conserte
> ANTES do merge — esses padrões produzem regressões invisíveis em dev que só aparecem depois de
> 10+ min de uso. Para **auditar uma regressão já em produção** ("fica lento depois de X min",
> "preciso dar F5", memória crescendo), use a skill `frontend-performance-audit`.

| Check                                                                 | Bug que previne                                                          |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Context `value` é `useMemo` com deps primitivas?                      | Cascade re-render em todos consumers a cada render do parent             |
| `<Provider value={{ ... }}>` SEM `useMemo`?                           | Mesma cascade — `value` muda a cada render                               |
| `useQuery` com `refetchInterval` consumido em route component?        | Toda tick re-renderiza a tree inteira em vez de só o leaf                |
| `setInterval` em route component (não em leaf memoizado)?             | Idem acima                                                               |
| Custom store com `this.field = x` fora do `setState(partial)` único?  | Invariant break → loop de stale check → request storm em produção        |
| `defaultPreloadStaleTime: 0` no router?                               | Hover em nav link dispara `beforeLoad` toda vez = request burst          |
| `beforeLoad` faz fetch ou muta async store sem gate por timestamp?    | Request storm em hover/preload                                           |
| Heavy children (charts, tables) sem `React.memo` ou com props inline? | Re-mount a cada parent render → leak de ResizeObserver                   |
| `<ResponsiveContainer>` (Recharts) sem cleanup verificado?            | ResizeObserver leak; mount count cresce sem unmount par                  |
| `useSyncExternalStore` retornando objeto novo a cada call?            | Tearing ou re-render em todo notify do store                             |
| Lista usando `index` como `key`?                                      | Re-mount errado em reorder, perda de state                               |
| `useEffect + setState` para derived state (em vez de `useMemo`)?      | Render extra + risco de loop                                             |
| `useEffect + fetch` em vez de TanStack Query?                         | Sem cache, sem dedup, sem retry, sem stale; refetch manual em todo lugar |

> **Render budget orientativo:** initial route load ≤ 15 renders do route component; polling tick ≤ 2
> renders (leaf only); hover preload ≤ 0 renders. Acima disso = bug.

Vários "render storms" se resolvem com primitives do React 19 (`useOptimistic` para rollback
automático, `useActionState` no lugar de `useState(loading) + useState(error) + useEffect`) — ver
skill `react-19-patterns` antes de refatorar componente com muitos `useState` + `useEffect`.
