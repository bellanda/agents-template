---
name: frontend-performance-ultimate
description: Plan-mode audit AND preventive checklist for React/TanStack frontend performance — re-render storms, request waves, store invariant breaks, and resource leaks that only show up after long sessions. Use when the user reports "fica lento depois de um tempo", "preciso dar F5", "abas demoram pra abrir", "tab idle e voltar trava", high CPU on idle, growing memory, or any symptom that survives a clean reload but degrades over use. Also use proactively as a checklist before merging changes that touch context providers, polling hooks, custom stores, or chart-heavy routes.
---

# Frontend Performance Ultimate — React + TanStack

This skill has two modes:

1. **Preventive checklist** (next section) — quick reference for code review and proactive auditing.
2. **Plan-mode audit** (Phases 1–5 below) — full diagnostic flow when a regression is already in production. Output is a prioritized punch list with `arquivo:linha`, evidence, mechanism, fix, and ordering. The user reviews and accepts before any edit.

## Preventive Checklist — Block These Before They Ship

Run this list whenever you touch a context provider, a polling hook, a custom store, or a chart-heavy route. If any item fails, fix BEFORE merging — these patterns produce regressions invisible in dev that only surface after 10+ minutes of use.

| Check                                                                 | Bug it prevents                                                          |
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

> **Render budget orientativo:** initial route load ≤ 15 renders do route component; polling tick ≤ 2 renders (leaf only); hover preload ≤ 0 renders. Acima disso = bug.

---

## Plan-Mode Audit (when regression is already in production)

This sub-skill produces a **plan**, not code. Output is a prioritized punch list of fixes, each with `arquivo:linha`, evidence, mechanism, fix, and ordering. The user reviews and accepts before any edit.

## When this skill applies

User reports any of:

- "Fica lento depois de 10/15min idle" / "preciso dar F5"
- "Quando volto pra aba o app trava"
- "Console enche de logs/warnings com o tempo"
- "Memória cresce sem parar"
- "Cada clique parece disparar 30 requests"
- High CPU when nothing is happening
- Re-render counts that grow with session age (not with user actions)

**Do NOT use this skill** for:

- First-paint / bundle-size / SSR optimization (different tree of causes — Lighthouse-style audit)
- Pure CSS/layout jank (use a paint-profiling skill)
- Network bottlenecks where the backend itself is slow (audit backend first)

## Why this is a separate skill

Perf bugs in long-lived SPAs do not show up in dev. They emerge from the interaction of: store invariants, context value identity, polling cadence, router preload behavior, observer lifecycles, and `useEffect` dep chains. Reading any single file in isolation misses the loop. This skill enforces a **system-level capture-then-analyze** flow before any local edit is proposed.

---

## The Skill Flow

### Phase 1 — Instrument (TEMPORARY — remove in Phase 5)

Instrumentation is a **diagnostic tool**, not production code. It is added to capture one (1) measurement window and removed afterwards. Never ship it as "always on, just in case" — every `console.log` on a hot path costs frames and pollutes user consoles, and a `setInterval` heartbeat keeps the tab from idling correctly.

Two acceptable shapes:

1. **Throwaway branch** (preferred): create the helper + wiring on a `chore/perf-audit` branch, capture, analyze, then **delete the branch** (or revert the instrumentation commits). Nothing reaches `main`.
2. **Gated helper** (only if the team wants reusable instrumentation): keep `debug.ts` but make it a true no-op in production — `DEBUG` resolves to a compile-time `false` in prod builds so Vite/Rollup tree-shakes every call site. No `setInterval`, no event listeners, no log strings constructed. The opt-in flag (`window.__DEBUG__`) only works in dev or in a special debug build.

Either way, **do NOT merge instrumentation to `main` as default-on**. If the user pushes back ("but I want it always available"), agree only on the gated form, with prod reduced to `if (false) { ... }` after dead-code elimination — verify with `bun run build` + grep the bundle for `debug:` strings (should be zero).

Add (or verify presence of) a debug helper at `src/lib/debug.ts`:

```ts
const DEBUG =
    (import.meta as any).env.MODE !== "production" ||
    (window as any).__APP_DEBUG__;
const T0 = performance.now();
const counters: Record<string, number> = {};

export function debugLog(category: string, msg: string, extra?: unknown) {
    if (!DEBUG) return;
    const t = ((performance.now() - T0) / 1000).toFixed(2);
    console.log(`[debug:${category}] +${t}s ${msg}`, extra ?? "");
}
export function debugCount(key: string): number {
    counters[key] = (counters[key] ?? 0) + 1;
    return counters[key];
}
export function debugDumpCounters() {
    console.table(counters);
}
if (typeof window !== "undefined") {
    (window as any).__APP_DEBUG_COUNTERS__ = counters;
}
```

Wire instrumentation at these exact points:

| Location                                      | What to log                                                                                                           | Counter key                    |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| `ApiClient.request` (start + end)             | `→ METHOD path`, `← status path {ms}` with `reqId`                                                                    | `http:request`                 |
| Auth refresh path (start + ok + fail)         | `refresh START`, `refresh OK`, `refresh FAIL`                                                                         | `auth:refresh`                 |
| Auth event listener                           | `auth-change event #N {detail}`                                                                                       | `auth:event`                   |
| Provider/DataProvider boot                    | `bootstrap fetchCurrentUser` + start/end of fetch                                                                     | `provider:fetchCurrentUser`    |
| Each `useQuery`'s `queryFn`                   | `fire <key>`, `done <key> {ms}`                                                                                       | `queryFn:<key>`                |
| Route component body                          | `render #N {sinceLastMs}`                                                                                             | `dashboard:render` (per-route) |
| `LazyMount` enter                             | `mount #N`                                                                                                            | `lazymount:trigger`            |
| Chart `<ChartContainer>` mount/unmount effect | `mount <id>`, `unmount <id>`                                                                                          | `chart:mount`, `chart:unmount` |
| `visibilitychange` listener                   | `tab HIDDEN` / `tab VISIBLE`                                                                                          | —                              |
| Heartbeat (every 30s)                         | TanStack cache stats: `totalQueries, fetching, stale, totalObservers`, recharts surfaces, `performance.memory.usedMB` | —                              |
| Counter dump (every 60s)                      | `debugDumpCounters()`                                                                                                 | —                              |

The heartbeat is non-negotiable — it is the only way to see growth between user actions.

### Phase 2 — Capture

Hand the instrumented build to the user with these instructions:

> 1. `bun run build && bun run serve` (production build — dev StrictMode doubles renders and obscures the picture).
> 2. Open the affected route, leave the tab focused 10–15 minutes.
> 3. Interact briefly at the start (set the baseline), then let it idle.
> 4. Come back, click around 2–3 times, and copy the **entire** browser console.
> 5. Also grab `window.__APP_DEBUG_COUNTERS__` from the console.

Wait for the log. Do not analyze speculatively.

### Phase 3 — Analyze the log against these heuristics

Read top-to-bottom, highlight evidence, then cross-reference code.

**A. Render storms**

- `render #N` count > 15 in initial load → route component is consuming too many `useQuery` directly. Action: split into memoized sections.
- Tight cluster of renders on a polling tick (`sinceLastMs ≈ refetchInterval`) → polling hook lives in a non-leaf component.
- Renders without any `queryFn fire` or user input → context `value` not memoized, or store snapshot not stable.

**B. Request waves**

- N requests fire within ~50ms with no user click → cascade triggered by a single state change. Find the trigger (auth event, route enter, context change).
- Same endpoint hit with growing `reqId` on a fixed cadence → polling. Cross-check `refetchInterval` placement.
- Auth refresh in a loop (auth-change events spaced exactly N seconds apart) → store setter bypass + router preload + stale check loop.

**C. Auth/store invariants**

- `auth-change` events on a fixed period with no user action → `isStale()` always true. Check the setter — any `this.x = y` outside `setState` is the bug.
- `refresh` happening but `getCurrentUser` never following → handler not closing `isLoading` → consumers stuck.

**D. Resource leaks**

- `chart:mount - chart:unmount` delta growing across heartbeats → leaked Recharts ResizeObservers.
- `totalObservers` (TanStack Query) growing without bound → component not unmounting or duplicate subscriptions.
- `performance.memory.usedMB` trending up across heartbeats with no user activity → real leak, not GC pressure.

**E. Router-driven storms**

- Burst of `beforeLoad` runs on mouse hover over nav → `defaultPreloadStaleTime: 0`.
- `beforeLoad` runs that always trigger an async store mutation → `beforeLoad` is doing work it shouldn't.

**F. Context cascade**

- Provider `value` re-creates every render (object literal in JSX) → all consumers re-render.
- One fat context with `{ user, theme, client, ... }` → split into multiple contexts.

### Phase 4 — Produce the plan

Output exactly this structure (use plan mode):

```
## Root cause(s)
<one line each, ranked by impact>

## Findings
For each finding:
- arquivo:linha
- evidência (snippet from log + snippet from code)
- mecanismo (why this causes the symptom)
- fix mínimo (smallest change that breaks the loop)
- blast radius (what re-renders / re-fetches today vs after fix)

## Apply order
1. Invariant fixes (store setters, single-mutation) — these unblock everything else
2. Context memoization
3. Polling isolation
4. Router preload tuning
5. Component split / React.memo
6. Chart / observer cleanup

## Verification
For each fix: what to look for in a fresh capture (counter delta, heartbeat trend, render count budget).
```

Never include code in Phase 4. Plan only. The user re-engages a normal coding turn to apply.

### Phase 5 — Teardown (REQUIRED)

After fixes are applied and a follow-up capture confirms the metrics moved in the right direction, **remove the instrumentation**:

- Delete `src/lib/debug.ts` (or revert the `chore/perf-audit` branch).
- Strip every `debugLog`/`debugCount`/`debugDumpCounters` call site.
- Remove the heartbeat `setInterval`, the `visibilitychange` listener, and the `window.__APP_DEBUG_COUNTERS__` assignment.
- Verify with `rg "debug(Log|Count|Dump)" src/` (should be zero) and a fresh `bun run build` (bundle should not contain `debug:` strings).

If the team explicitly chose the **gated helper** form in Phase 1, Phase 5 still applies to call sites that were one-shot diagnostics (e.g., the per-route `render #N`, the chart mount/unmount). Only structural instrumentation that's genuinely useful long-term (and proven dead-code-eliminated in prod) may stay. **Default is: strip everything.**

---

## Hard rules for this skill

- **No edits in Phase 1–4.** Only the instrumentation hook (Phase 1) is an edit, and only if `lib/debug.ts` is missing.
- **Instrumentation is temporary.** Phase 5 is not optional. Production builds must not ship the heartbeat, the per-render log, or any active `setInterval` from this skill. Default outcome: branch deleted or files reverted after the audit closes.
- **Never analyze without a real capture.** Speculation produces wrong root causes.
- **Always run capture against a production build.** StrictMode double-renders mask the real numbers.
- **One root cause is rarely the whole story.** Even after the obvious loop is fixed, expect 1–2 secondary smells (un-memoized context, polling at the wrong level). Surface them in the same plan.
- **Quantify before recommending.** "Render count went from 70 → 12" beats "should be faster". The instrumentation is the proof.
- **Do not recommend large refactors.** Each fix is surgical. If a refactor is genuinely needed (route component owns 10 queries), call it out separately and let the user decide.

## Common patterns this skill catches

| Symptom in log                                           | Root cause                                                                   | Fix                                                                |
| -------------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `auth-change` every 10s, no user action                  | Store setter bypass — `isStale()` perpetually true                           | Single-mutation invariant in store setter                          |
| 70 renders on initial load, 41 chart mount/unmount pairs | Route component re-renders on every settled query, dragging chart subtree    | `React.memo` on chart wrappers + memoize `data`/`config`           |
| Burst of N requests after hovering nav link              | `defaultPreloadStaleTime: 0` + `beforeLoad` touching async store             | Raise to 60_000, make `beforeLoad` cheap                           |
| `totalObservers` grows on every navigation               | Component subscribing to `useQuery` without cleanup, or duplicate hook calls | Ensure single owner per query key in the tree                      |
| `performance.memory.usedMB` grows on idle                | Leaked observer (Recharts ResizeObserver, IntersectionObserver)              | Verify cleanup in `useEffect`, audit `chart:mount/unmount` balance |
| Context consumers re-render on every parent render       | `<Provider value={{...}}>` inline                                            | `useMemo` the value object with primitive deps                     |
| Polling tick re-renders entire dashboard                 | `useQuery` with `refetchInterval` consumed at route level                    | Move the hook into a memoized leaf component                       |

## Stack assumed

React 19 + TanStack Router + TanStack Query + Vite. Auth via custom singleton + `useSyncExternalStore` is supported but flagged for migration to Zustand on any new store.

## Skills relacionadas

- **`react-19-patterns`** — vários "render storms" hoje se resolvem com `useOptimistic` (rollback automático) ou `useActionState` (substitui `useState(loading) + useState(error) + useEffect`). Invoque antes de propor refactoring de componente com muitos `useState` + `useEffect`.
- **`shadcn` > [rules/charts.md](../shadcn/rules/charts.md)** — receita canônica para wrap de Recharts (memo, useMemo data, useMemo config, useCallback handlers) que previne o `chart:mount/unmount` delta crescente flagado neste skill.
- **`shadcn` > [rules/magic-ui.md](../shadcn/rules/magic-ui.md)** — Magic UI canvas components (`<Globe>`, `<Particles>`) são suspeitos #2 de leak (depois de Recharts). Aplicar mesma checklist: 1 por viewport, lazy abaixo da fold, key estável em lists animadas.
