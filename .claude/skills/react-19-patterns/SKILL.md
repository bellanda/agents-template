---
name: react-19-patterns
description: React 19 primitives — `use()`, `useActionState`, `useOptimistic`, `useFormStatus`, Form Actions, `useTransition`, ref-as-prop, Context-as-Provider, document metadata. INVOKE BEFORE writing or refactoring any of these patterns — form com submit async, data fetching fora de TanStack Query, optimistic UI, `useEffect + fetch`, `useEffect + setState` para derived state, `useState(loading) + useState(error)` em form, `forwardRef`, `<Context.Provider>`. Não re-derive padrão; siga a tabela de decisão.
---

# React 19 Patterns

React 19 reposicionou `useEffect` como ferramenta de **sincronização com sistema externo** (WebSocket, lib DOM 3rd-party, focus imperativo) — não como Swiss Army knife. Quase tudo que era `useEffect + useState` antes agora tem primitive dedicado.

Esta skill é o manual de uso desses primitives. Cada sub-rule = padrão + exemplo before/after + quando NÃO usar.

## Tabela de Decisão Mestra

| Problema concreto                                                            | Use                                       | Sub-rule                          |
| ---------------------------------------------------------------------------- | ----------------------------------------- | --------------------------------- |
| Data fetching client-side (route, list, detail page)                         | **TanStack Query** (default do projeto)   | —                                 |
| Data fetching server-driven (route loader passa Promise pro componente)      | `use(promise)` + `<Suspense>` + `<ErrorBoundary>` | [data-fetching.md](./rules/data-fetching.md) |
| Form com submit async + pending + error + success                            | `useActionState` + Form Action            | [forms.md](./rules/forms.md)      |
| Pending state em componente filho do `<form>` (botão, status badge)          | `useFormStatus`                           | [forms.md](./rules/forms.md)      |
| Optimistic UI (like, vote, mark read, drag-reorder)                          | `useOptimistic`                           | [optimistic.md](./rules/optimistic.md) |
| Filtros/tabs pesados que travam input ao mudar                               | `useTransition` / `startTransition`       | [transitions.md](./rules/transitions.md) |
| Componente que precisa receber `ref` (input, button, scroll target)          | `ref` como prop direto (sem `forwardRef`) | [ref-and-context.md](./rules/ref-and-context.md) |
| Context Provider                                                             | `<MyContext value={...}>` (sem `.Provider`) | [ref-and-context.md](./rules/ref-and-context.md) |
| Document title / meta tag / link tag por rota                                | `<title>` / `<meta>` / `<link>` inline no JSX | [ref-and-context.md](./rules/ref-and-context.md) |
| Sync com sistema externo (WebSocket, ChartLib, focus, Intersection/Resize)   | `useEffect` (uso legítimo, único restante) | —                                 |
| Refactoring `useEffect` legado                                               | **Classifique pela tabela.** Sync externo → manter. Caso contrário → migrar. | [migration.md](./rules/migration.md) |

## Quando NÃO invocar esta skill

- TanStack Query já cobre o caso → use TanStack Query, não `use()`. `use()` é para fluxo server-driven (loader passa Promise como prop). Em SPA Vite puro, TanStack Query é quase sempre a resposta — `use()` entra raramente.
- `useEffect` com cleanup de WebSocket / ChartLib / `addEventListener` — uso legítimo, não migre.
- Componente legado funcionando: surgical edits only (`agent-behavior.md`). Só migre se já for tocar o arquivo por outro motivo, OU se o user pediu refactoring explícito.

## Princípio

> Componente React 19 é uma **descrição declarativa de UI dado o estado/dados**. Loading flags, error variables, cleanup de race condition, manual rollback — tudo isso são responsabilidades do runtime React (Suspense, Error Boundary, Actions). Se você está escrevendo plumbing, está usando o primitive errado.

## Stack assumida

React 19 (kailos: 19.2.6) + TypeScript 7 (TSGo no kailos, TS 5.9+ resto) + Vite 8 + TanStack Router/Query/Form. SPA, não Next.js / RSC server-side. Form Actions funcionam client-only — não confundir com Next.js Server Actions.

## Sub-rules

- [rules/data-fetching.md](./rules/data-fetching.md) — `use(promise)` + Suspense + Error Boundary
- [rules/forms.md](./rules/forms.md) — `useActionState` + Form Actions + `useFormStatus`
- [rules/optimistic.md](./rules/optimistic.md) — `useOptimistic` + rollback automático
- [rules/transitions.md](./rules/transitions.md) — `useTransition` / `startTransition` em filtros pesados
- [rules/ref-and-context.md](./rules/ref-and-context.md) — ref-as-prop, Context-as-Provider, document metadata
- [rules/migration.md](./rules/migration.md) — catálogo "sintoma `useEffect` X → primitive Y"
