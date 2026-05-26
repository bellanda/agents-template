# Migration Catalog — `useEffect` legado → primitive certo

Catálogo de sintomas comuns e qual primitive React 19 resolve. Aplicar de forma cirúrgica: só migre se já for tocar o arquivo, OU se o user pediu refactoring explícito. Refactoring em massa de `useEffect` é PROIBIDO sem aprovação.

## Catálogo

| Sintoma no código                                                                                       | Migrar para                                       | Motivo                                                                                       |
| ------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `useEffect(() => { fetch(...).then(setData) }, [id])` + `useState(loading)` + `useState(error)`         | TanStack Query (default) OU `use()` + Suspense    | Race condition, sem cache, sem dedup, sem retry                                              |
| `useEffect(() => setSomething(deriveFrom(prop)), [prop])`                                               | `useMemo` ou inline                               | Renderiza 2x, gera state duplicado de algo derivável                                         |
| `useEffect(() => { if (condition) setFlag(true) }, [condition])`                                        | inline durante render: `const flag = condition`   | Idem                                                                                         |
| `useEffect` que recoloca `value` em form depois de fetch (`setForm(data)`)                              | `useActionState` (form async) OU `key` + uncontrolled  | Sync entre fetch e form via effect é frágil                                                  |
| `useEffect` + `setIsSubmitting(true/false)` em handler de submit                                        | `useActionState` + `<form action={fn}>`           | 1 hook substitui 3 useState + try/finally                                                    |
| `useState(count)` + `setCount(n+1)` antes do `await`, `setCount(n)` no catch                            | `useOptimistic`                                   | Rollback manual frequentemente errado quando prop external muda                              |
| `useEffect` + `setTimeout` para debounce de input pesado                                                | `useTransition` (e mantém `setQuery` direto)      | Não precisa debouncar — React processa em background                                         |
| `useEffect` que faz `document.title = "..."` na entry da rota                                           | `<title>` inline no JSX                           | React 19 hoist nativo                                                                        |
| `useEffect` que chama `el.focus()` em mount quando `isOpen`                                             | **Manter** `useEffect` (sync com sistema externo) | DOM focus é imperativo — uso legítimo                                                        |
| `useEffect` com `new WebSocket(url)` / `EventSource` / lib chart                                        | **Manter** `useEffect`                            | Sync com sistema externo — uso legítimo, exemplo canônico                                    |
| `useEffect` que conecta `IntersectionObserver` / `ResizeObserver` / `MutationObserver`                  | **Manter** `useEffect`                            | Browser API — uso legítimo                                                                   |
| `useEffect` que `addEventListener` em `window` / `document`                                             | **Manter** `useEffect`                            | Browser API — uso legítimo                                                                   |
| `useState(items)` + `useEffect` de sync com prop `items` quando muda                                    | Reading prop direto ou `key` prop pra resetar     | "lifting state up" mal feito, leva a state stale                                             |
| `useState(loading)` + `useEffect` que faz `setLoading(true)` antes de query manual                      | TanStack Query `isPending` / `isFetching`         | Reinventou TanStack Query                                                                    |
| `useEffect` que faz `setData(prev => prev.filter(...))` em response de mutation                         | `useOptimistic` + `useMutation` `onSuccess` invalidate | Optimistic + invalidação resolvem isso                                                       |

## Workflow de migração

Quando for migrar (autorizado ou tocando o arquivo já):

1. **Classifique** o `useEffect` pela tabela acima.
2. **Se "manter":** documente o porquê em comment (se ainda não tem), só pra futuro-você não tentar migrar de novo. Ex: `// useEffect legítimo: sync com WebSocket externo`.
3. **Se migrar:**
   - Aplique o primitive correspondente.
   - Remova `useState(loading)` / `useState(error)` redundantes.
   - Verifique que `bun typecheck` e `bun lint` passam.
   - Verifique no browser que o comportamento é IDÊNTICO (loading state aparece, error state aparece, success state aparece nos mesmos pontos).
4. **Commit pequeno:** 1 migração por commit, mensagem explica qual primitive substituiu o quê.

## NÃO fazer

- Refactoring em massa de N arquivos numa PR só. Cada migração tem seu risco; bundle = perda de revisabilidade.
- Migrar form que está funcionando "porque agora tem `useActionState`". Surgical edits only.
- Migrar `forwardRef` em componente legado só para "modernizar". A regra é: código novo usa ref-as-prop; código velho fica.
- Adicionar `useTransition` "por garantia" em todo lugar. Use APENAS onde o input demonstrável trava.

## Quando o user pede refactoring agressivo

Pedidos tipo "refactora tudo pra React 19" → primeiro **relatório**: top N `useEffect` migráveis por arquivo, classificado. User decide PR por PR. Não fazer refactoring autônomo sem aprovação explícita por escopo.
