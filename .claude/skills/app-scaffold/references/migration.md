# Migrating an existing project to the standard app shell

Most existing projects already have the **sidebar shape right** — shadcn `<Sidebar collapsible="icon">`, `components/sidebar/app-sidebar.tsx`, `components/layouts/sidebar-layout.tsx`, `SidebarProvider` + `SidebarInset`. The migration is therefore mostly about the **auth contract** and the **route split**, not the sidebar markup.

## What is already consistent (leave it)

- shadcn `Sidebar collapsible="icon"`, Header / Content / Footer regions.
- `SidebarProvider` + `SidebarInset` + `SidebarTrigger` app shell.
- `useAuth()` as the public hook name, footer user dropdown with logout.
- TanStack Router, React 19, Tailwind v4.

## What differs (normalize it)

Auth contract is **already standard** in kailos/promoservice/akmeo/balizap: `useAuth()` over
`useDataProvider()`, `authStore` (vanilla, `ready` gate in `main.tsx`) and `access-token-store.ts`.
(An earlier revision of this file prescribed a zustand `persist` store — wrong, never built, and
persisting tokens is an XSS hole. Corrected 2026-10-01.) A project that deviates: copy those three
files + `useAuth.ts` from kailos.

| Off-standard | Standard |
| --- | --- |
| `beforeLoad` polls/awaits network or can't read auth synchronously | `main.tsx` awaits `authStore.ready`; `beforeLoad` reads `authStore.getState()` |
| Token in localStorage / zustand `persist` | Token in memory (`access-token-store.ts`), refresh in HttpOnly cookie |
| Guard scattered per-route or absent | One `beforeLoad` on the `_authenticated` (or `/app`) layout route |
| Authenticated routes at top level | Nested under the layout route |

## Steps

1. **Auth modules.** Copy `lib/api/access-token-store.ts`, `lib/auth/auth-store.ts`, `hooks/useAuth.ts`, `lib/api/context.tsx` from kailos; gate `RouterProvider` on `authStore.ready` in `main.tsx`.
2. **Route split.** Add `_authenticated.tsx` (pathless; or `app/route.tsx`) with the single `beforeLoad` guard + `<SidebarLayout>`. Reduce `__root.tsx` to bare `<Outlet/>`. Move authenticated route files under it.
3. **Fix references.** The TanStack Router Vite plugin rewrites `createFileRoute` ids on file move, but **`Link to=`, `redirect({ to })`, `navigate({ to })`, and `useParams({ from })` must be updated by hand**. `bunx tsgo --noEmit` flags every stale one.
4. **Regenerate + verify.** `bun run routes:gen`, then `bunx tsgo --noEmit`, then `bun run build`.

## Per-project notes

- **Multi-org projects** — keep the `ROUTES` constant object; the multi-org sidebar (org selector / collapsible org list) stays — only the auth layer and route split change.
- **Chat / dual-mode projects** — no `ROUTES` constant and a dual-mode sidebar (platform nav vs chat threads); preserve that, migrate only auth + guard.
- A **multi-org** sidebar swaps the static brand `SidebarHeader` for an org-selector component — everything else (Content groups, Footer dropdown, `collapsible="icon"`) is identical to the reference.
