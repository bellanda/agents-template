# Frontend — TypeScript, React, TanStack & Architecture

> Cada linha sublinhada aponta a skill com a implementação completa. Invoque a skill ANTES de escrever código.

## Stack

| Layer        | Tool                         | Skill / nota                                                                                                                                                                          |
| ------------ | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Language     | **TypeScript 7 (TSGo)**      | `@typescript/native-preview` quando disponível. `camelCase` em tudo; `snake_case` só no boundary da API.                                                                              |
| Pkg Manager  | **bun**                      | `bun add/dev/run`. NUNCA npm/yarn/pnpm.                                                                                                                                               |
| Runtime      | **React 19**                 | Functional, hooks, named exports. Primitives: `use()`, `useActionState`, `useOptimistic`, `useFormStatus`, Form Actions, ref-as-prop, Context-as-Provider. Skill `react-19-patterns`. |
| Build        | **Vite 8 (Rolldown)**        | `@/` → `src/`. `VITE_*` em `app.yaml > vite:`.                                                                                                                                        |
| Router       | **TanStack Router**          | File-based, `beforeLoad` para auth.                                                                                                                                                   |
| Data         | **TanStack Query**           | TODA data fetching client-side. `useEffect + fetch` é PROIBIDO.                                                                                                                       |
| Forms        | **TanStack Form + Zod 4**    | `validators: { onChange: zodSchema }`. NUNCA react-hook-form; `zod-form-adapter` é legado.                                                                                            |
| Styling      | **Tailwind CSS 4**           | CSS-first config (sem `tailwind.config.ts`). Skill `tailwind-4-setup`.                                                                                                                |
| UI base      | **Shadcn/ui 4**              | Semantic CSS vars only. Skill `shadcn`.                                                                                                                                               |
| UI especial  | **Magic UI**                 | Animated List, Ticker, Marquee, Globe, Shimmer. Extende registry Shadcn.                                                                                                              |
| Charts       | **Shadcn Charts** (Recharts) | `ChartContainer` + `ChartConfig` + `ChartTooltip`. Skill `shadcn` (sub-rule `charts.md`).                                                                                             |
| Animation 2D | **Motion** (`motion`)        | NÃO `framer-motion`. CSS-first.                                                                                                                                                       |
| Visual 3D    | **Three.js + R3F + drei**    | Skill `threejs-r3f-patterns`. Para visual "vivo" sem 3D, prefira Magic UI.                                                                                                            |
| Icons        | **react-icons**              | Lucide, FA, MD, Phosphor, Tabler via 1 package.                                                                                                                                       |
| Input masks  | **react-imask**              | CPF, phone, dates.                                                                                                                                                                    |

## Invariantes não negociáveis

- **Componentes**: <200 ideal | 200–350 monitor | 350–500 split | 500+ proibido. Named exports. Typed props. `interface` para shapes, `type` para uniões. Sem `any` — `unknown` + type guard. `@/` absolute imports (NUNCA `../../../`).
- **React 19**: `ref` como prop direto (`forwardRef` LEGADO). `<MyContext value={...}>` direto (`.Provider` LEGADO). Document metadata inline (`<title>`/`<meta>` hoisted, NÃO use `react-helmet`). Form async / data fetch fora de Query / optimistic / `useEffect + fetch` ou `useEffect + setState` → skill `react-19-patterns`.
- **State**: 5 níveis (local/URL/server/UI/outside-react) — skill `frontend-state-management`. TODA API data em TanStack Query (NUNCA duplicar em Context/store). Filtros/pagination em URL (`useSearch`). Context com `value` SEMPRE `useMemo`.
- **Overlays**: Dialog-first (forms, snippets, confirm, detail, picker). Sheet/Drawer só com justificativa escrita. Skill `dialog-first-overlays`.
- **Auth**: access token em memória (NUNCA localStorage/sessionStorage/Zustand persist). Refresh on 401 via `withRefreshLock` (Web Locks API). Cookie HttpOnly path-scopado SameSite=Strict. Skill `auth-hardened`.
- **Performance**: polling em leaf memoizado (NUNCA route component); Context `value` SEMPRE `useMemo`; heavy children com `React.memo` + props estáveis; charts: mount==unmount ao longo do tempo. Render budget: route load ≤ 15 renders, polling tick ≤ 2. Sintoma "fica lento depois de X min" / "preciso dar F5" → skill `frontend-performance-ultimate`.
- **Tailwind 4**: CSS-first config (`@import "tailwindcss"` + `@theme inline` com OKLCH). Container queries para componentes; viewport breakpoints para página. Semantic shadcn vars (`bg-background`); NUNCA raw colors. Skill `tailwind-4-setup`.
- **Code blocks** (`<pre>` / snippet copiável): SEMPRE `whitespace-pre-wrap break-all` no `<pre>` + `<code>`. NUNCA `overflow-x-auto` (scroll horizontal em código copiável = UX ruim). Vertical (`overflow-y-auto`) OK.
- **DateTime**: API entrega ISO 8601 com `Z`. NUNCA offset math manual. Display via `Intl.DateTimeFormat` em utility module (`formatDateTime`, `formatDate`). Null/invalid → fallback `"—"`.

## TanStack Router

- Auth em `beforeLoad` ONLY (zero flash). `throw redirect(...)`.
- `beforeLoad` cheap + idempotente. SEM fetch, SEM mutação async de store por entrada.
- `defaultPreloadStaleTime: 60_000` mínimo (`0` = request storm em hover).
- Stores (`organizationStore`, `authStore`) lidos dentro de `beforeLoad` (fora do React).

## API Layer

- `camelCase` ↔ `snake_case` no `ApiClient` ONLY. Components/hooks sempre `camelCase`.
- `client.get<T>()` → `ApiResponse<T>`: `{ data, status, success }`.
- Lists → `PagedResponse<T>`: `{ items, total, skip, limit }`.
- Adapter (baseURL+headers) → ApiClient (fetch+key rename) → Query function (extrai `res.data`) → `useCrud` (paged pattern).

## Naming

Components `PascalCase` | Hooks `usePrefix` | Stores `kebab-store` | Types `PascalCase` | Constants `UPPER_CASE` | Routes `kebab-case`/`$param`. UI strings em pt-BR. `ROUTE_PATHS` constants para todas as rotas.

## Formatter (Prettier) — CRITICAL FOR EDIT TOOLS

2-space indent (spaces only) | double quotes | 100 char line length | semicolons | trailing commas (es5)
