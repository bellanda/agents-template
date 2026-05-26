# Frontend — TypeScript, React, TanStack & Architecture

> **Toda vez que tocar frontend, leia este arquivo + invoque a skill correspondente ao trigger:**
>
> | Trigger                                                                                                       | Skill                           |
> | ------------------------------------------------------------------------------------------------------------- | ------------------------------- |
> | Form async, data fetch fora de TanStack Query, optimistic UI, `useEffect` que faz fetch ou deriva state       | `react-19-patterns`             |
> | Adicionar / compor / debugar shadcn component, Magic UI, Shadcn Charts                                        | `shadcn`                        |
> | UI com peso estético/de marca — landing, hero, dashboard novo, login flow, scene 3D                          | `frontend-design`               |
> | "Fica lento depois de X min", "preciso dar F5", memória cresce, CPU alta idle, regressão de performance      | `frontend-performance-ultimate` |
>
> Falso positivo custa tokens; falso negativo custa correção. **Na dúvida, invoque.**

## Stack

| Layer       | Tool                       | Rule                                                                                                                                                                               |
| ----------- | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Language     | **TypeScript 7 (TSGo)**       | `@typescript/native-preview` quando disponível (kailos já usa) — fallback TS 5.9+. `camelCase` em tudo. `snake_case` só no boundary da API (ApiClient) |
| Pkg Manager  | **bun**                       | `bun add`, `bun dev`, `bun run`. NEVER npm/yarn/pnpm                                                                                                  |
| Runtime      | **React 19**                  | Functional components, hooks, named exports only. Primitives novos: `use()`, `useActionState`, `useOptimistic`, `useFormStatus`, Form Actions, ref-as-prop, Context-as-Provider. Ver tabela "React 19 — Decisão" abaixo |
| Build        | **Vite 8 (Rolldown/Rust)**    | `@/` alias → `src/`. `VITE_*` lidos de `app.yaml > vite:` em `vite.config.ts` (single source). Docker build usa build args (`compose.{env}.yaml > nginx.build.args`) como fallback |
| Router       | **TanStack Router**           | File-based, type-safe, `beforeLoad` para auth                                                                                                         |
| Data         | **TanStack Query**            | TODA data fetching client-side. `useEffect + fetch` é PROIBIDO                                                                                        |
| Forms        | **TanStack Form + Zod 4**     | `@tanstack/react-form` com validators inline (`validators: { onChange: zodSchema }`). `@tanstack/zod-form-adapter` é LEGADO (v0.x) — não usar em código novo. NUNCA react-hook-form |
| Styling      | **Tailwind CSS 4**            | CSS-first config (`@theme` em CSS, sem `tailwind.config.ts` em projeto novo). Utility-only, mobile-first. Container queries (`@container/`) preferidos para componentes que adaptam ao container |
| UI base      | **Shadcn/ui 4**               | Registry oficial. Semantic CSS variables only, sem raw colors. Ver skill `shadcn`                                                                     |
| UI especial  | **Magic UI**                  | Componentes "com personalidade" (Animated List, Number Ticker, Marquee, Globe, Shimmer Button). Extende registry Shadcn. Ver `shadcn/rules/magic-ui.md` |
| Charts       | **Shadcn Charts** (wrapper Recharts) | `ChartContainer` + `ChartConfig` + `ChartTooltip`. Semantic colors via CSS vars. Ver `shadcn/rules/charts.md`                                  |
| Animation 2D | **Motion**                    | CSS-first, Motion lib (`motion`, não `framer-motion`) para interações complexas                                                                       |
| Visual 3D    | **Three.js + R3F**            | `three` + `@react-three/fiber` + `@react-three/drei` para 3D/shaders/partículas/scene avançado. Ver seção "Visual Avançado / 3D" abaixo               |
| Icons        | **react-icons**               | Todos icon sets via 1 package (Lucide, FA, MD, Phosphor, Tabler…)                                                                                     |
| Input masks  | **react-imask**               | CPF, phone, dates                                                                                                                                     |

## Component Rules

- **Size:** < 200 ideal | 200–350 monitor | 350–500 split now | 500+ proibido.
- Split via form sections (`<BasicInfoSection>`) ou sub-components.
- Named exports only. Typed props. `@/` absolute imports — NUNCA relative `../../../`.
- `interface` para shapes; `type` para uniões/aliases. Sem `any` — use `unknown` + type guard.
- **`ref` como prop direto (React 19).** `forwardRef` é LEGADO — em código novo, declare `ref` como prop normal e use direto. Componente que aceita ref: `function Input({ ref, ...props }: InputProps) { return <input ref={ref} {...props} /> }`.
- **`<MyContext>` como Provider direto (React 19).** `<MyContext.Provider>` é LEGADO — use `<MyContext value={...}>`. Continua valendo a regra de memoizar o `value`.
- **Document metadata inline.** `<title>`, `<meta>`, `<link>` no JSX do componente são hoisted automaticamente. Não use `react-helmet`.

## React 19 — Tabela de Decisão

Antes de escrever `useEffect + useState`, ver se o caso cai num primitive React 19. Detalhes (before/after, gotchas, when NOT to use) na skill **`react-19-patterns`** — invoque ANTES de codar.

| Problema                                                          | Use                                                                |
| ----------------------------------------------------------------- | ------------------------------------------------------------------ |
| Data fetching client-side                                         | **TanStack Query** (default). Cache, dedup, retry, stale resolvidos |
| Data fetching server-driven (route loader passa Promise pra child)| `use(promise)` + `<Suspense>` + `<ErrorBoundary>`                  |
| Form submit async + pending + error + success                     | `useActionState` + Form Action (`<form action={fn}>`)              |
| Pending state em componente filho do form (botão, status badge)   | `useFormStatus` (dentro do `<form>`)                               |
| Optimistic UI (like, vote, mark read)                             | `useOptimistic` — rollback automático em erro                      |
| Transition pesada (filtros, tabs com muitos itens)                | `useTransition` / `startTransition`                                |
| Sync com sistema externo (WebSocket, lib DOM 3rd-party, focus)    | `useEffect` (uso legítimo, único caso restante)                    |
| Derived state                                                     | `useMemo` ou inline — NUNCA `useEffect + setState`                 |
| Refactoring `useEffect` legado                                    | Antes de tocar, classifique pela tabela. Sync externo → manter. Caso contrário → migrar via primitive correspondente. Surgical, não em massa. |

## Overlays — Dialog-First (regra forte)

**Dialog é o default** para qualquer superfície que aparece por cima do conteúdo: forms secundários, snippets/code-blocks, detail views, confirmações, pickers complexos, "abrir e fechar". Centralizado, foco visual claro, dismiss por click-fora/ESC retorna o usuário ao estado exato anterior. UX superior em quase todos os casos.

| Cenário                                                         | Use                                                   |
| --------------------------------------------------------------- | ----------------------------------------------------- |
| Form curto/médio, snippet, confirm, detail, picker, share, edit | **Dialog**                                            |
| Tooltip rápido, info inline, hint                               | Popover / HoverCard                                   |
| Menu de ações contextual (right-click, ⋯)                       | DropdownMenu / ContextMenu                            |
| Inspector lateral PERSISTENTE durante navegação (raro)          | Sheet (com justificativa explícita: por que persiste) |
| Wizard mobile multi-step com gestures de swipe                  | Drawer (vaul) — mobile-only flow                      |

`Sheet` e `Drawer` só com motivo escrito: "precisa ficar lado-a-lado com o conteúdo" ou "mobile-only flow longo com swipe". Para tudo que é "abre, faz uma coisa, fecha" → **Dialog**, sem discussão.

Width sugerida: `lg:max-w-2xl` default · `lg:max-w-3xl xl:max-w-4xl` para snippet/code/table-heavy · `sm:max-w-md` para confirm/pick simples · NUNCA full-screen exceto wizard real. Conteúdo alto → `max-h-[85vh] overflow-y-auto` no `DialogContent`.

## Code blocks — wrap, nunca scroll horizontal

Em qualquer `<pre>` / code block (snippet copiável, instrução SQL, payload JSON):

- **SEMPRE** `whitespace-pre-wrap` + `break-all` (ou `[overflow-wrap:anywhere]`) no `<pre>` **e** no `<code>` interno.
- **NUNCA** `overflow-x-auto` / `overflow-x-scroll`. Scroll horizontal em código copiável = UX ruim: o usuário arrasta pra ler, perde contexto da linha, e a quebra "esconde" o que foi cortado.
- Vertical (`overflow-y-auto` no container) é OK. Linhas longas (curl com `-d '<json>'`, URL completa, JSON inline) precisam quebrar visualmente — o conteúdo copiado pelo botão preserva as quebras de linha originais.
- Em Shiki, aplicar via seletor: `[&_pre]:whitespace-pre-wrap [&_pre]:break-all [&_code]:whitespace-pre-wrap [&_code]:break-all`.

Se a linha for tão longa que `break-all` quebra em locais ruins, melhor refatorar o gerador do snippet pra inserir quebras explícitas (`\` em bash, vírgula+`\n` em JSON multiline) do que ligar scroll horizontal.

## State Management

| Level         | Tool                          | When                                             |
| ------------- | ----------------------------- | ------------------------------------------------ |
| Local         | `useState`                    | Modals, toggles — single component               |
| URL           | `useSearch` (TanStack Router) | Filters, pagination — sobrevive refresh          |
| Server        | TanStack Query                | TODA API data — NUNCA duplicar em Context/stores |
| Deep UI       | React Context                 | State 3+ níveis deep                             |
| Outside React | Zustand stores                | Auth tokens, org ID para API calls               |

## Performance — Checklist Obrigatório

- NUNCA `useEffect + fetch`. TanStack Query only (ou `use()` + Suspense em fluxo server-driven).
- `useEffect` só para sincronizar com sistema externo (Browser API, lib não-React, WebSocket, focus imperativo). Para qualquer outro caso, ver "React 19 — Tabela de Decisão" acima e migrar para o primitive correspondente.
- Derived state → inline ou `useMemo`. Events → handlers. NUNCA `useEffect + setState` ou `useEffect + flag`.
- **Form async** → `useActionState` + Form Action (`<form action={fn}>`), não `useState(loading)` + `useState(error)` + manual orchestration.
- **Optimistic UI** → `useOptimistic` — rollback é automático em erro, não escrever rollback manual.
- Lists → ID estável como key, nunca index.
- `exhaustive-deps` warnings = bugs — nunca suprimir.
- **Context `value` SEMPRE `useMemo` com deps primitivas.** `<Provider value={{...}}>` inline = re-render storm em todos os consumers.
- **Polling vive em leaf memoizado.** `useQuery` com `refetchInterval` ou `setInterval` NUNCA no route component — todo tick re-renderiza a tree inteira.
- **Route component = orquestrador** (lê URL, renderiza sections). Cada section dona da própria query.
- **Heavy children** (charts, tables) com `React.memo` + props estáveis (`useMemo` data, `useCallback` handlers).
- Chart `mount` count == `unmount` count ao longo do tempo. Delta crescente = leak (Recharts ResizeObserver é o suspeito #1).
- **Custom store: single-mutation invariant.** Todo set passa por `setState(partial)` que também atualiza derived (timestamps, dirty flags). Nunca `this.field = x` fora dele. Para store novo, prefira **Zustand**.
- `useSyncExternalStore` snapshot deve ser referencialmente estável.
- **Render budget:** initial route load ≤ 15 renders; polling tick ≤ 2 renders (leaf only); hover preload ≤ 0 renders.

> Sintomas de "fica lento depois de X min", "preciso dar F5", memória cresce, CPU alta idle
> → INVOCAR skill `frontend-performance-ultimate` antes de tocar código.

## Auth — Invariantes

Pareado com `backend.md > Auth`. Implementação completa (store, bootstrap, lock, BroadcastChannel, hooks de login/logout) na **skill `auth-hardened`** — invocar antes de tocar `access-token-store`, `use-bootstrap`, interceptor de 401, login/logout flow.

- **Access token em memória** (`lib/api/access-token-store.ts`). NUNCA `localStorage`/`sessionStorage`/Zustand `persist`.
- **Bootstrap no mount**: `POST /api/v1/auth/token/refresh` antes do `<RouterProvider />`. Cookie HttpOnly viaja sozinho. `<AppRoot>` espera `isReady` — sem flash logado→deslogado.
- **Refresh on 401**: `ApiClient.fetch` intercepta → `withRefreshLock(refreshAccessToken)` (Web Locks API: `navigator.locks.request("auth:refresh", {mode:"exclusive"}, fn)`) → re-tenta uma vez. 3 requests paralelos = 1 `/refresh`.
- **Multi-tab**: `BroadcastChannel("<project>-auth")` (namespaced) propaga `setAccessToken` e logout entre abas.
- **Zustand auth store**: identidade do user only (id, name, email, roles), sem token, sem `persist`.
- **Logout**: `POST /auth/session/logout` → `setAccessToken(null)` + `queryClient.clear()` + broadcast + redirect.

### Don'ts

- **NUNCA** `localStorage.setItem("access_token", ...)`. Memória only.
- **NUNCA** ler refresh token no JS — é HttpOnly.
- **NUNCA** chamar `/refresh` em paralelo sem `withRefreshLock`.
- **NUNCA** `persist` em Zustand auth store.
- **NUNCA** redirect manual no 401 — interceptor retenta com refresh primeiro.

## TanStack Router — Regras

- Auth em `beforeLoad` ONLY (zero flash). `throw redirect(...)`.
- `beforeLoad` cheap + idempotent. SEM fetch, SEM mutação async de store por entrada. Validação por `isStale` com timestamp real.
- `defaultPreloadStaleTime: 60_000` mínimo. `0` = request storm em hover.
- Stores (`organizationStore`, `authStore`) lidos dentro de `beforeLoad` (estão fora do React).

## API Layer

- `camelCase` ↔ `snake_case` conversion no `ApiClient` ONLY. Components/hooks sempre `camelCase`.
- `client.get<T>()` retorna `ApiResponse<T>`: `{ data, status, success }`.
- Lists retornam `PagedResponse<T>`: `{ items, total, skip, limit }`.
- Adapter: baseURL + headers. ApiClient: fetch + key rename. Query function: extrai `res.data`. useCrud: wrappa paged pattern.

## DateTime — Frontend

- API sempre entrega ISO 8601 com `Z`. **Frontend NUNCA faz offset math manual.**
- Display via `Intl.DateTimeFormat` — auto-converte para timezone do user.
- Toda formatação em **uma utility module** (`formatDateTime`, `formatDate`, `formatDateLong`). Components importam, nunca inline.
- Null/undefined/invalid date → fallback consistente (`"—"`), nunca `"Invalid Date"`.
- User input local → `.toISOString()` antes de mandar para backend.

## Naming

Components `PascalCase` | Hooks `usePrefix` | Stores `kebab-store` | Types `PascalCase` | Constants `UPPER_CASE` | Routes `kebab-case`/`$param`
UI strings em pt-BR. `ROUTE_PATHS` constants para todas as rotas.

## Tailwind 4 — CSS-First Config

Em projeto novo, **sem `tailwind.config.ts`**. Config vive em CSS.

- `@import "tailwindcss"` no `index.css` (substitui `@tailwind base/components/utilities` do v3).
- `@theme inline { ... }` define tokens com **OKLCH** para cores semantic:
  ```css
  @theme inline {
    --color-background: oklch(1 0 0);
    --color-foreground: oklch(0.145 0 0);
    --color-primary: oklch(0.205 0 0);
    /* ... */
  }
  ```
- **Container queries primeiro.** `@container/name` no parent + `@sm:`, `@md:` no child. Reservar viewport breakpoints (`sm:`, `md:`, `lg:`) para layout de **página**, não para componente.
- Mobile-first: base styles para mobile, scale up com `sm:` → `md:` → `lg:` → `xl:` → `2xl:`. NUNCA inverta.
- Sempre semantic Shadcn CSS variables (`bg-background`, `text-foreground`, `border-border`). Nunca raw colors (`bg-blue-500`).
- `tailwind.config.ts` só sobrevive em projeto legado que tem plugin v3 sem equivalente v4. Greenfield = CSS-only.

## Visual Avançado / 3D — Three.js

Para 3D, shaders, animações de partículas, scene interativa:

- **Default:** `three` + `@react-three/fiber` (R3F) + `@react-three/drei` (helpers).
- Component pattern: `<Canvas><Mesh>...</Mesh></Canvas>` declarativo, não imperative `THREE.Scene()`.
- Animation loop via `useFrame`, NUNCA `requestAnimationFrame` solto.
- Cleanup: R3F já dispõe geometry/material no unmount; ainda assim, observar `useEffect` cleanup para listeners customizados.
- **Quando NÃO usar Three.js:** animação 2D normal (Motion), micro-interaction de hover/transition (CSS), card com brilho/glow (Magic UI). Three.js é para cenas que justificam o custo do WebGL context.
- Para visual "vivo" sem chegar em 3D: **Magic UI** (extende Shadcn) — Marquee, Globe, Number Ticker, Animated Beam, Shimmer Button, etc.

Skill `ui-ux-pro-max` mantém `data/stacks/threejs.csv` como referência expandida.

## Formatter (Prettier) — CRITICAL FOR EDIT TOOLS

2-space indent (spaces only) | double quotes | 100 char line length | semicolons | trailing commas (es5)
