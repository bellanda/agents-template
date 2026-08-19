# Migrating an existing project to the standard app shell

Most existing projects already have the **sidebar shape right** — shadcn `<Sidebar collapsible="icon">`, `components/sidebar/app-sidebar.tsx`, `components/layouts/sidebar-layout.tsx`, `SidebarProvider` + `SidebarInset`. The migration is therefore mostly about the **auth contract** and the **route split**, not the sidebar markup.

## What is already consistent (leave it)

- shadcn `Sidebar collapsible="icon"`, Header / Content / Footer regions.
- `SidebarProvider` + `SidebarInset` + `SidebarTrigger` app shell.
- `useAuth()` as the public hook name, footer user dropdown with logout.
- TanStack Router, React 19, Tailwind v4.

## What differs (normalize it)

| Off-standard | Standard |
| --- | --- |
| `useAuth()` resolves from a `DataProvider` **React Context** holding auth state | `useAuth()` is a composition hook over the zustand `useAuthStore`; no auth Context |
| Auth state (`user`, token) in Context / a vanilla class store | Tokens + user snapshot in zustand `persist` store |
| `beforeLoad` can't synchronously read auth, or uses a workaround | `beforeLoad` reads `useAuthStore.getState()` directly |
| Guard scattered per-route or absent | One `beforeLoad` on the `/app` layout route |
| Authenticated routes at top level (`/dashboard`, `/leads`, ...) | Nested under `/app/*` |

## Steps

1. **Auth store.** Create `src/stores/auth.ts` — zustand + `persist`, holding `accessToken`, `refreshToken`, `user` snapshot, `setSession()`, `clear()`. Port whatever the old `DataProvider` / class store held.
2. **`useAuth()` hook.** Replace the Context-backed `useAuth()` with the composition hook (`references/useAuth.ts`). Keep the **name and return shape** as close as possible (`{ user, isAuthenticated, login, logout }`) so call sites barely change. Delete the `DataProvider` auth Context and its `<Provider>` wrapper.
3. **Login flow.** On successful login, call `setSession(...)`; the ApiClient and `beforeLoad` now read the store.
4. **Route split.** Add `app/route.tsx` with the single `beforeLoad` guard + `<SidebarLayout>`; add `app/index.tsx` redirecting to the default authenticated route. Reduce `__root.tsx` to bare `<Outlet/>`. Move authenticated route files under `src/routes/app/**`.
5. **Fix references.** The TanStack Router Vite plugin rewrites `createFileRoute` ids on file move, but **`Link to=`, `redirect({ to })`, `navigate({ to })`, and `useParams({ from })` must be updated by hand**. `bunx tsgo --noEmit` flags every stale one (the router is typed).
6. **Regenerate + verify.** `bun run routes:gen`, then `bunx tsgo --noEmit`, then `bun run build`.

## Per-project notes

- **Multi-org projects** — keep the `ROUTES` constant object; the multi-org sidebar (org selector / collapsible org list) stays — only the auth layer and route split change.
- **Chat / dual-mode projects** — no `ROUTES` constant and a dual-mode sidebar (platform nav vs chat threads); preserve that, migrate only auth + guard.
- A **multi-org** sidebar swaps the static brand `SidebarHeader` for an org-selector component — everything else (Content groups, Footer dropdown, `collapsible="icon"`) is identical to the reference.
