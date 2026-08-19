---
name: app-scaffold
description: Scaffold da casca de um app React 19 + TanStack Router — split público-vs-autenticado com UM beforeLoad guard, sidebar shadcn collapsible-to-icon (header brand / nav groups / footer user dropdown), o contrato useAuth() (token em memória + cookie HttpOnly, NUNCA persist; zustand só para leitura fora de hook), e a landing pública full-screen (rota fora da casca, Particles + wordmark + CTA único → /login). Use ao montar a navegação de um app novo, adicionar sidebar, padronizar a casca de um projeto existente, ou criar a tela inicial/hero/splash. Triggers — "sidebar", "app shell", "casca de app", "padronizar navegação", "app layout", "landing", "tela inicial", "hero com particles", "splash". O layout/largura/enquadramento (1440, SidebarLayout/SidebarChatLayout) vêm do gate `frontend`; a direção estética da landing vem de `ui-ux-pro-max`; instalações de componente vêm de `shadcn`.
---

# App Scaffold — Casca Autenticada + Landing Pública

Scaffold canônico das duas superfícies de um app React 19 + TanStack Router + shadcn: a **landing
pública** (Parte B) e a **casca autenticada** (Parte A). Uma navegação, um split de rota, um contrato
de auth — aplicados igual entre projetos.

> **Divisão de responsabilidade:** o **layout/largura/enquadramento** (1440, `SidebarLayout`,
> `SidebarChatLayout`, header) é do gate `frontend` → `references/layouts.tsx`. **Este skill** cuida
> de: split de rota, guard de auth, contrato `useAuth()`, o componente `<AppSidebar>` (nav/brand/user),
> e a rota de landing. Estética da landing → `ui-ux-pro-max`. Instalações → `shadcn`.

---

## Parte A — Casca autenticada

### Os três pilares

| Pilar | Regra |
| --- | --- |
| **Split de rota** | `__root.tsx` é `<Outlet/>` puro. Rotas públicas (`/`, `/login`) renderizam full-screen, sem casca. Um layout route autenticado (`_authenticated.tsx` pathless — o que balizap/kailos usam; ou `/app` pathed) é dono da casca + o único guard. Toda rota autenticada nasce sob ele. |
| **Contrato `useAuth()`** | Token de acesso em **memória**, refresh em **cookie HttpOnly** (ver gate `auth`). Zustand guarda o token em memória + um snapshot do user para leitura fora de hook (`beforeLoad`, ApiClient via `.getState()`). `useAuth()` é um **composition hook** fino sobre o store — NUNCA um Context provider. |
| **Sidebar** | shadcn `<Sidebar collapsible="icon">` — Header (brand) / Content (nav groups) / Footer (user dropdown). Montada dentro do layout do gate. |

### Arquitetura de rota

```
src/routes/
  __root.tsx              → createRootRoute({ component: () => <Outlet /> })   — sem casca
  index.tsx               → "/"        landing pública (Parte B)
  login.tsx               → "/login"   full-screen, sem casca
  _authenticated.tsx      → layout route: beforeLoad guard + <SidebarLayout> (gate)
  _authenticated/<feat>.tsx
```

- O guard vive **uma vez** no layout route; todo filho herda:
  ```tsx
  beforeLoad: () => {
    if (!useAuthStore.getState().accessToken) throw redirect({ to: "/login" });
  }
  ```
- Rotas públicas redirecionam usuário **já autenticado** pra dentro: `index.tsx`/`login.tsx`
  `beforeLoad` → `throw redirect({ to: "/dashboard" })`.
- `beforeLoad` roda **fora do React** — lê o store via `.getState()`, nunca `useAuth()` nem hook.
- Alternativa pathed `/app/route.tsx` (prefixo visível na URL) é válida — escolha UMA; o guard fica
  num lugar só de qualquer forma.

### `useAuth()` — o contrato de auth

Token de sessão é lido fora do React (`beforeLoad`, ApiClient) → **zustand**. O user é o principal da
sessão → snapshot pequeno **junto** do token, no mesmo store. Um React Context com `{ user, logout }`
re-renderiza todo consumer a cada mudança — **nunca faça isso**.

```tsx
export function useAuth() {
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const clear = useAuthStore((s) => s.clear);
  const login = useLogin(); // TanStack Query mutation
  return { user, isAuthenticated: !!accessToken, login, logout: clear };
}
```

- `stores/auth.ts` — zustand, guarda `accessToken` (memória), `user` snapshot; `setSession()`,
  `clear()`. **SEM `persist`** de token — access em memória, refresh em cookie HttpOnly path-scopado
  (gate `auth`). Persistir token em localStorage = vulnerabilidade a XSS.
- Componentes (sidebar, header) chamam `useAuth()`. `beforeLoad` chama `useAuthStore.getState()`.
- Logout = `clear()` **e então** `navigate({ to: "/" })` — limpar o store não navega.

### `<AppSidebar>` — `components/sidebar/app-sidebar.tsx`

`<Sidebar collapsible="icon">` com três regiões:

- **Header** — brand: ícone num quadrado `bg-sidebar-primary` arredondado + nome. O ícone fica visível
  quando colapsa pro rail de ícones.
- **Content** — um ou mais `<SidebarGroup>` → `<SidebarMenu>`. Cada item é `<SidebarMenuButton asChild
  tooltip={label} isActive={...}>` envolvendo um `<Link>`. **`tooltip` é obrigatório** — é o label
  mostrado quando colapsado. `isActive` vem de `useRouterState({ select: s => s.location.pathname })`.
- **Footer** — `<DropdownMenu>` cujo trigger é `<SidebarMenuButton size="lg">` com `<Avatar>` + nome +
  email; menu com Logout `DropdownMenuItem variant="destructive"`.

Nav items como constante de módulo tipada — greppável, um lugar pra editar:

```tsx
const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LuLayoutDashboard },
  { to: "/catalog", label: "Catalog", icon: LuTable2 },
] as const;
```

Mobile: leia `useSidebar()` para `{ isMobile, setOpenMobile }`; feche o drawer ao navegar.

### Setup (projeto novo)

1. Invoque **`shadcn`** → `init`, depois `add sidebar dropdown-menu breadcrumb avatar`. Reconcilie o
   CSS global pros tokens `--color-sidebar-*` existirem. **Envolva o root (`main.tsx`) em
   `<TooltipProvider>`** — o `tooltip` do `SidebarMenuButton` renderiza um `<Tooltip>` e o
   `SidebarProvider` não embute um `TooltipProvider`.
2. Copie `references/useAuth.ts`, `references/app-sidebar.tsx`; adapte brand + `NAV_ITEMS`. Use o
   layout do gate (`frontend` → `references/layouts.tsx`).
3. Crie o layout route (guard + `<SidebarLayout>`) e o redirect index → dashboard; reduza
   `__root.tsx` a `<Outlet/>` puro.
4. Mova as rotas autenticadas; o plugin Vite do TanStack reescreve os ids, mas **corrija à mão**
   `Link to=` e `useParams({ from })`.
5. `bun run routes:gen` então `bunx tsgo --noEmit` — o router tipado acusa todo link velho.

Aplicar a projeto **existente** (esp. um usando `DataProvider` auth Context): `references/migration.md`.

---

## Parte B — Landing pública (epic startup)

Tela de entrada pública em `/`, full-screen, atmosférica, que existe pra UMA coisa: levar o visitante
ao `/login`. **Fora** da casca. Estrutura/contrato aqui; **direção estética** (paleta, tipografia,
motion) vem de `ui-ux-pro-max` — comprometa-se com uma direção bold e específica.

### Contrato

| Regra | Detalhe |
| --- | --- |
| **Pública, sem casca** | `src/routes/index.tsx`, filho direto do `__root.tsx` puro. Sem sidebar/header. |
| **Redireciona autenticado** | `beforeLoad` → se `useAuthStore.getState().accessToken`, `throw redirect({ to: "/dashboard" })`. |
| **Um CTA** | Um único `<Button asChild>` envolvendo `<Link to="/login">`. Sem ação secundária competindo. |
| **Full-screen** | `relative min-h-screen w-full overflow-hidden` (glow/particles não geram scrollbar). |

### Composição em camadas (trás → frente)

1. **Base** — fundo sólido. Cena escura → escope: `<div className="dark ... bg-background">` (vars
   `.dark` aplicam localmente mesmo em app light).
2. **Particles** — magic-ui `<Particles className="absolute inset-0 z-0" />`. `color` contrasta a base
   (`#ffffff` no escuro); `quantity` ~120–160.
3. **Glow radial** — um `radial-gradient` suave atrás do wordmark (`blur-3xl`, baixa opacidade).
4. **Vignette** — `radial-gradient(ellipse at center, transparent ~40%, var(--background) 100%)` sobre
   `inset-0` pra puxar o foco pro centro.
5. **Conteúdo** — `relative z-10`, coluna centrada: eyebrow → wordmark → subtitle → CTA.

Camadas decorativas: `aria-hidden` + `pointer-events-none`.

### Stack de conteúdo

- **Eyebrow** — pequeno, uppercase, tracking largo, muted. Bom lugar pra uma assinatura do produto.
- **Wordmark** — nome do produto, bem grande (`text-6xl`→`text-8xl`), `font-bold tracking-tight`.
  Distinção por escala/tracking + um tratamento de accent (ex.: gradiente `bg-clip-text
  text-transparent` em parte do nome) — não uma segunda fonte, salvo se o design system já tiver.
- **Subtitle** — exatamente uma linha, `text-balance`, muted, diz o que o produto é. Locale do projeto.
- **CTA** — `<Button size="lg" asChild>` + `<Link to="/login">` + `ArrowRight` trailing.

### Motion de entrada

Um reveal orquestrado de page-load bate micro-interações espalhadas. Stagger os 4 elementos com
`tw-animate-css` (`animate-in fade-in-0 slide-in-from-bottom-3 duration-700 fill-mode-both`) + um
`style={{ animationDelay }}` explícito por elemento (0/100/200/300ms — inline porque o `delay-*` do
Tailwind mira `transition-delay`, não `animation-delay`).

### Setup

1. **`shadcn`** → add Particles: `bunx shadcn@latest add "https://magicui.design/r/particles"`. No
   arquivo gerado, troque `NodeJS.Timeout` por `ReturnType<typeof setTimeout>` (projeto browser-only).
2. **`ui-ux-pro-max`** → comprometa-se com uma direção estética.
3. Copie `references/landing-route.tsx` pra `src/routes/index.tsx`; adapte wordmark/subtitle/accent.
4. Verifique: `/` full-screen sem casca; CTA chega no `/login`; visitante autenticado é redirecionado.

---

## References

- `references/app-sidebar.tsx` — template do `<AppSidebar>`.
- `references/useAuth.ts` — o composition hook.
- `references/migration.md` — aplicar a casca a projeto existente; migrar de auth Context (`DataProvider`).
- `references/landing-route.tsx` — template completo da rota de landing.

> O layout (`SidebarLayout`/`SidebarChatLayout`, 1440, `fullBleed`) é do gate `frontend` →
> `references/layouts.tsx`. Não duplique aqui.
