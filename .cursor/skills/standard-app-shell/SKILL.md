---
name: standard-app-shell
description: Standardized authenticated app shell for React + TanStack Router projects — shadcn collapsible-to-icon sidebar, public-vs-`/app` route split with a single `beforeLoad` guard, `SidebarProvider`/`SidebarInset` layout (header with trigger + breadcrumb, footer user dropdown), and the `useAuth()` contract (zustand tokens + composition hook, never a React Context). Use when scaffolding a new app's navigation shell, adding a sidebar, or standardizing an existing project's layout/auth. Triggers on "sidebar", "app shell", "casca de app", "padronizar navegação", "app layout". Pairs with the `shadcn` skill (component installs) and `epic-startup-landing` (the public entry route).
---

# Standard App Shell

The canonical authenticated shell for React 19 + TanStack Router + shadcn/ui projects. One sidebar pattern, one route split, one auth contract — applied identically across projects so navigation, auth, and layout are never re-derived.

Reference implementation: the standard React + TanStack frontend. Some existing projects use the same sidebar shape but read auth from a `DataProvider` **Context** — that is the pattern to migrate **away from** (see `references/migration.md`).

## The three pillars

| Pillar | Rule |
| --- | --- |
| **Route split** | `__root.tsx` is bare `<Outlet/>`. Public routes (`/`, `/login`) render full-screen, no shell. A pathed `/app` layout route owns the shell + the single auth guard. Every authenticated route nests under `/app/`. |
| **`useAuth()` contract** | Tokens live in a zustand store (`useAuthStore`) — `beforeLoad` and the ApiClient read `useAuthStore.getState()` directly. `useAuth()` is a thin **composition hook** over the store, never a Context provider. |
| **Sidebar** | shadcn `<Sidebar collapsible="icon">` — Header (brand) / Content (nav groups) / Footer (user dropdown). Mounted via `<SidebarProvider>` + `<SidebarInset>` in `sidebar-layout.tsx`. |

## Route architecture

```
src/routes/
  __root.tsx          → createRootRoute({ component: () => <Outlet /> })   — no shell
  index.tsx           → "/"        public landing (see epic-startup-landing)
  login.tsx           → "/login"   full-screen, no shell
  app/
    route.tsx         → "/app"     layout route: beforeLoad guard + <SidebarLayout>
    index.tsx         → "/app/"    redirect → /app/dashboard
    dashboard.tsx     → "/app/dashboard"
    <feature>.tsx     → "/app/<feature>"
```

- The **`/app` prefix is visible in the URL** — use a pathed `app/route.tsx`, not a pathless `_authenticated.tsx`.
- The guard lives **once** on `app/route.tsx` and every `/app/*` child inherits it:
  ```tsx
  beforeLoad: () => {
    if (!useAuthStore.getState().accessToken) throw redirect({ to: "/login" });
  }
  ```
- Public routes redirect **authenticated** users inward: `index.tsx` and `login.tsx` `beforeLoad` → `throw redirect({ to: "/app/dashboard" })`.
- `beforeLoad` runs **outside React** — it reads the store via `.getState()`, never `useAuth()` or a hook.

## `useAuth()` — the auth contract

Tokens are session state needed outside React (`beforeLoad`, ApiClient) → **zustand**. The user object is the session principal → kept as a small snapshot **alongside the tokens** in the same store. A React Context holding `{ user, logout, can }` re-renders every consumer on any change — **never do that**.

`useAuth()` is the only public API inside React — a composition hook, ~15 lines:

```tsx
export function useAuth() {
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const clear = useAuthStore((s) => s.clear);
  const login = useLogin(); // TanStack Query mutation
  return { user, isAuthenticated: !!accessToken, login, logout: clear };
}
```

- `stores/auth.ts` — zustand + `persist`, holds `accessToken`, `refreshToken`, `user`; `setSession()`, `clear()`.
- Components (sidebar, header) call `useAuth()`. `beforeLoad` calls `useAuthStore.getState()`.
- Logout = `clear()` **then** `navigate({ to: "/" })` — clearing the store does not navigate.

## `<AppSidebar>` — `components/sidebar/app-sidebar.tsx`

`<Sidebar collapsible="icon">` with three regions:

- **Header** — brand block: an icon in a `bg-sidebar-primary` rounded square + name. The icon stays visible when collapsed to the icon rail.
- **Content** — one or more `<SidebarGroup>` → `<SidebarMenu>`. Each item is `<SidebarMenuButton asChild tooltip={label} isActive={...}>` wrapping a TanStack `<Link>`. **`tooltip` is mandatory** — it is the label shown when collapsed to icons. Compute `isActive` from `useRouterState({ select: s => s.location.pathname })`.
- **Footer** — `<DropdownMenu>` whose trigger is a `<SidebarMenuButton size="lg">` showing `<Avatar>` + name + email; menu has a Logout `DropdownMenuItem variant="destructive"`.

Nav items as a typed module constant — greppable, one place to edit:

```tsx
const NAV_ITEMS = [
  { to: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/app/catalog", label: "Catalog", icon: Table2 },
] as const;
```

Mobile: read `useSidebar()` for `{ isMobile, setOpenMobile }`; close the drawer on navigation.

## `<SidebarLayout>` — `components/layouts/sidebar-layout.tsx`

`<SidebarProvider>` → `<AppSidebar />` + `<SidebarInset>`. The `SidebarInset` holds:

- a `h-14` header: `<SidebarTrigger />` + vertical `<Separator />` + `<Breadcrumb>` derived from the pathname (drop the `/app` prefix, map segments to labels);
- `<main>` with `<Outlet />` (constrained, e.g. `mx-auto w-full max-w-[1500px] px-4 py-4`).

`app/route.tsx`'s component is just `<SidebarLayout><Outlet /></SidebarLayout>`.

## File conventions

| File | Purpose |
| --- | --- |
| `src/routes/__root.tsx` | bare `<Outlet/>` |
| `src/routes/app/route.tsx` | `/app` layout route — guard + `<SidebarLayout>` |
| `src/components/sidebar/app-sidebar.tsx` | the sidebar |
| `src/components/layouts/sidebar-layout.tsx` | provider + inset + header |
| `src/hooks/useAuth.ts` | composition hook |
| `src/stores/auth.ts` | zustand token + user store |

## Setup steps (new project)

1. Invoke the **`shadcn`** skill → `init`, then `add sidebar dropdown-menu breadcrumb avatar`. Reconcile the global CSS so the `--color-sidebar-*` tokens exist. **Then wrap the app root (`main.tsx`) in `<TooltipProvider>`** — `SidebarMenuButton`'s `tooltip` prop renders a `<Tooltip>` and the radix-nova `SidebarProvider` does **not** bundle a `TooltipProvider` (the CLI prints this reminder on `add`).
2. Copy `references/useAuth.ts`, `references/app-sidebar.tsx`, `references/sidebar-layout.tsx`; adapt brand + `NAV_ITEMS`.
3. Create `app/route.tsx` (guard + layout) and `app/index.tsx` (redirect to dashboard); reduce `__root.tsx` to bare `<Outlet/>`.
4. Move authenticated routes under `src/routes/app/**`; the TanStack Router Vite plugin rewrites `createFileRoute` ids on move, but **fix internal `Link to=` and `useParams({ from })`** by hand.
5. `bun run routes:gen` then `bunx tsgo --noEmit` — the typed router flags every stale link.

Applying to an **existing** project (esp. one using a `DataProvider` auth Context): see `references/migration.md`.

## References

- `references/app-sidebar.tsx` — the sidebar template (from the reference frontend).
- `references/sidebar-layout.tsx` — the provider/inset/header template.
- `references/useAuth.ts` — the composition hook.
- `references/migration.md` — applying the shell to an existing project; migrating off a `DataProvider` auth Context.
