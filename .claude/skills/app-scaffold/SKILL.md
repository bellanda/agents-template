---
name: app-scaffold
description: Scaffold da casca de um app React 19 + TanStack Router — split público-vs-autenticado com UM beforeLoad guard, sidebar shadcn collapsible-to-icon (header brand / nav groups / footer user dropdown), o contrato useAuth() (token em memória + cookie HttpOnly, NUNCA persist; `authStore`/`access-token-store` vanilla para leitura fora de hook), o seletor de organização (`org-selector` + `NewOrgDialog`), permissão em 2 níveis (`can()` + `beforeLoad`), notificações + push/PWA, e a landing pública (rota fora da casca; splash mínima ou landing com seções → `/auth/login`). Use ao montar a navegação de um app novo, adicionar sidebar, padronizar a casca de um projeto existente, ou criar a tela inicial/hero/splash. Triggers — "sidebar", "app shell", "casca de app", "padronizar navegação", "app layout", "seletor de organização", "nova organização", "can()", "notificações", "push", "landing", "tela inicial", "hero com particles", "splash". O layout/largura/enquadramento (1440, SidebarLayout/SidebarChatLayout) vêm do gate `frontend`; a direção estética da landing vem de `ui-ux-pro-max`; instalações de componente vêm de `shadcn`.
---

# App Scaffold — Casca Autenticada + Landing Pública

Scaffold canônico das duas superfícies de um app React 19 + TanStack Router + shadcn: a **landing
pública** (Parte B) e a **casca autenticada** (Parte A). Uma navegação, um split de rota, um contrato
de auth — aplicados igual entre projetos. **Canônico de código = kailos** (`frontend/src/`);
infra comum de casca padronizada em 2026-10-01 (itens "Infra comum da casca" na Parte A).

> **Divisão de responsabilidade:** o **layout/largura/enquadramento** (1440, `SidebarLayout`,
> `SidebarChatLayout`, header) é do gate `frontend` → `references/layouts.tsx`. **Este skill** cuida
> de: split de rota, guard de auth, contrato `useAuth()`, o componente `<AppSidebar>` (nav/brand/user),
> e a rota de landing. Estética da landing → `ui-ux-pro-max`. Instalações → `shadcn`.

---

## Parte A — Casca autenticada

### Os três pilares

| Pilar | Regra |
| --- | --- |
| **Split de rota** | `__root.tsx` é `<Outlet/>` puro. Rotas públicas (`/`, `/auth/login`, `/auth/convite`) renderizam full-screen, sem casca. Um layout route autenticado (`_authenticated.tsx` pathless — o que balizap/kailos usam; ou `/app` pathed) é dono da casca + o único guard. Toda rota autenticada nasce sob ele. |
| **Contrato `useAuth()`** | Token de acesso em **memória**, refresh em **cookie HttpOnly** (ver gate `auth`). Dois módulos vanilla leem fora do React: `lib/api/access-token-store.ts` (token em memória, BroadcastChannel entre abas) e `lib/auth/auth-store.ts` (`authStore.getState()` → `{ user, isAuthenticated, isLoading, status }` + `ready`). `useAuth()` (`hooks/useAuth.ts`) é a API pública dentro do React. |
| **Sidebar** | shadcn `<Sidebar collapsible="icon">` — Header (brand) / Content (nav groups) / Footer (user dropdown). Montada dentro do layout do gate. |

### Arquitetura de rota

```
src/routes/
  __root.tsx              → createRootRoute({ component: () => <Outlet /> })   — sem casca
  index.tsx               → "/"            landing pública (Parte B)
  auth/login.tsx          → "/auth/login"  full-screen, sem casca (padrão 2026-10-01; era `/login`)
  auth/convite.tsx        → "/auth/convite" aceite de convite (token) — também pública
  _authenticated.tsx      → layout route: beforeLoad guard + <SidebarLayout> (gate)
  _authenticated/<feat>.tsx
```

- O guard vive **uma vez** no layout route; todo filho herda:
  ```tsx
  beforeLoad: () => {
    if (!authStore.getState().isAuthenticated) {
      throw redirect({ to: ROUTES.AUTH.LOGIN, search: { redirect: location.href } }); // "/auth/login"
    }
  }
  ```
- A rota de login é **`/auth/login`** em todos os apps (constante `ROUTES.AUTH.LOGIN` em
  `config/routes.ts`; irmã `ROUTES.AUTH.INVITE = "/auth/convite"`). `/login` solto não existe mais.
  O guard passa `redirect=<href atual>` para retomar a página depois do login.
- Rotas públicas redirecionam usuário **já autenticado** pra dentro: `auth/login.tsx`
  `beforeLoad` → `throw redirect({ to: "/dashboard" })` (a landing com seções é exceção — Parte B).
- `beforeLoad` roda **fora do React** — lê o store via `.getState()`, nunca `useAuth()` nem hook.
- Alternativa pathed `/app/route.tsx` (prefixo visível na URL) é válida — escolha UMA; o guard fica
  num lugar só de qualquer forma.

### `useAuth()` — o contrato de auth

Estado **real** nos 4 apps (kailos canônico; corrigido 2026-10-01 — a versão anterior deste skill
descrevia um `useAuthStore` zustand que NÃO existe no código):

- `lib/api/access-token-store.ts` — token em **memória** (`setAccessToken`/`getAccessToken`, sync entre
  abas via `BroadcastChannel`: refresh simultâneo em N abas revogaria a família). Nunca localStorage.
- `lib/auth/auth-store.ts` — classe vanilla `authStore` (`getState()`, `setState()`, `subscribe`,
  `ready: Promise`). `main.tsx` só monta o `RouterProvider` depois de `await authStore.ready` (bootstrap
  `/auth/token` → `/accounts/me`), então todo `beforeLoad` lê `getState()` **síncrono** — sem polling
  nem rede dentro do router (polling com deadline deslogava no mobile lento).
- `hooks/useAuth.ts` — `useAuth()` resolve de `useDataProvider()` (`lib/api/context.tsx`, o provider do
  ApiClient/`auth`) + TanStack Query (`login`/`logout` mutations; login zera token, cache e sessão
  server antes) e exporta também `useCurrentOrgRoles()` (`can()`). Refresh em cookie HttpOnly
  (gate `auth`).
- `beforeLoad` e services leem `authStore.getState()`; componentes chamam `useAuth()`. Nunca expose
  Context com `{ user, logout }` re-renderizando tudo — o provider só carrega o `DataProvider`.
- Client-side é UX (guard de rota), nunca autorização — o backend valida toda request.
- Logout = limpar sessão (`useAuth().logout`) **e então** `navigate({ to: "/" })` — limpar o store não navega.

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

### Infra comum da casca (padrão kailos — decisão 2026-10-01)

Os itens abaixo são parte da casca de TODO app multi-tenant autenticado. Copie do kailos, adapte só
nomes/endpoints.

**1. Seletor de organização + `NewOrgDialog`.**
- `components/sidebar/org-selector.tsx` no `SidebarHeader` (substitui o brand estático quando há
  multi-org): dropdown com as orgs do `user.organizations`, check na ativa, item **"Nova organização"**.
  Resolve a org selecionada **de forma síncrona no 1º render** (`organizationStore.ensureSelection(...)`
  no inicializador do `useState`, senão pisca "Sem organização" logo após o login) e sincroniza com
  o `:id` da rota quando existir.
- `stores/organization-store.ts` (`getSelectedOrgId`, `setSelectedOrgId`, `ensureSelection`,
  `subscribe`; persiste só o id) é a **fonte do tenant ativo** para o hub de settings, o inbox
  (`/chat`) e qualquer tela sem `$id` na rota. Hook: `useSyncExternalStore(subscribe, getSelectedOrgId)`.
- **Um** diálogo de criar org, `components/organizations/NewOrgDialog.tsx` (nome + slug + CNPJ
  opcional + endereço via `OrgIdentityFields`; `FormDialog`), aberto por `newOrgDialogStore.open()`
  (store mínimo `getIsOpen/open/close/subscribe` em `stores/new-org-dialog-store.ts`) e montado **uma
  vez** em `_authenticated.tsx` (`<NewOrgDialog mandatory={needsOnboarding} />`, `mandatory` = usuário
  sem org ainda: sem X, sem fechar). Nunca um segundo "criar org" (página `/organizations/new`,
  dialog alternativo) — quem precisa abrir chama `newOrgDialogStore.open()`.
- No layout autenticado montam também `<SettingsDialog />` (hub `?settings=`, ver
  `frontend/references/settings-dialog.md`) e, no `SidebarLayout`, `NotificationBell`,
  `NetworkStatusBanner` e `OrgBlockedBanner` (ver `frontend/references/feedback-states.md`).

**2. Permissão em DOIS níveis (mesma permissão nos dois).**
- **Nível UI — `can()`**: `const { can, isAdminLevel, isSuperuser } = useCurrentOrgRoles()` (`hooks/useAuth.ts`;
  lê `user` + `organizationStore` e devolve `can(permission)`). Esconde/desabilita botão, aba, item de
  nav e seção do hub. **Perguntar por PERMISSÃO** (`PERMISSIONS.MEMBER_MANAGE`, `QUEUE_MANAGE`…), nunca
  por papel (`role === "admin"`): o backend cobra permissão e conceder uma avulsa deve abrir a UI.
- **Nível rota — `beforeLoad`** com `hasOrgPermission(user, orgId, permission)` de
  `lib/auth/permissions.ts` (puro, fora do React; superusuário passa):
  ```tsx
  beforeLoad: ({ params }) => {
    const { user } = authStore.getState();            // .getState(), nunca hook
    if (!hasOrgPermission(user, params.id, PERMISSIONS.ASSESSMENT_APPROVE_EDIT)) {
      throw redirect({ to: "/organizations/$id/dashboard", params: { id: params.id } });
    }
  },
  ```
  O link da sidebar pode sumir (nível 1) e mesmo assim a URL digitada à mão cai no redirect (nível 2).
  A API é o terceiro nível e o único que protege dado (403) — gate de front é UX, não segurança.
- Quem ainda não tem o hook `useCurrentOrgRoles` (nexarena) ganha o mesmo, com a mesma assinatura.
- **Não existe componente `<Can>`**: `auth/Can.tsx` (balizap/promoservice) estava sem uso e foi
  apagado — se precisar de condicional, `can(...) && <X/>` inline.

**3. Notificações + push/PWA (kailos).**
- **Sino** `components/notifications/NotificationBell.tsx` no header do `SidebarLayout`: **Popover,
  nunca Sheet nem Dialog**; só a 1ª página (8) no popover (`useInfiniteList` com `POPOVER_PAGE_SIZE`),
  badge "99+", "marcar tudo como lido"; página cheia `routes/_authenticated/notificacoes.tsx` com o
  scroll infinito. `NotificationRow` é a linha única dos dois. Hooks em `hooks/useNotifications.ts`
  (`useUnreadCount`, `useMarkNotificationRead`, `useMarkAllNotificationsRead`).
- **Push** só com o app instalável: `hooks/usePushSubscription.ts` devolve um de **5 estados**
  (`unsupported | needs-install | denied | subscribed | default`, cada um por uma restrição real do
  iOS: PushManager só existe com o app na Tela de Início; `denied` é irreversível por JS → texto
  "Ajustes do aparelho", sem botão morto) + `subscribe/unsubscribe`. UI: `PushPermissionCard`
  (na página de notificações/perfil). Apoio: `hooks/useIsStandalone.ts` (`display-mode: standalone|
  minimal-ui` + `navigator.standalone` do iOS), `lib/push/register-sw.ts`, `lib/push/vapid.ts`,
  `public/sw.js` (`push` + `notificationclick`; o push ACORDA o SW) e `public/manifest.json`
  (`display: "minimal-ui"`, `start_url: "/dashboard"`, ícones 192/512/maskable com `?v=`, `lang: pt-BR`).
  Detalhe de PWA instalado (`minimal-ui` vs standalone, reload no iOS, safe-area) →
  `frontend/references/pwa-mobile.md`. Service worker **só** para push — nada de cache offline
  automático sem pedido explícito.
- Backend (VAPID, tabela de inscrições, entrega) → gate `integrations`/`infra`.

**4. O que a casca NÃO tem mais.** `ui/breadcrumb.tsx` (apagado nos 4 apps que o tinham sem uso),
`auth/Can.tsx`, `ui/bulk-action-bar.tsx` (akmeo; substituído por `BulkActionsMenu` no toolbar —
`frontend/references/list-screen.md`) e `documents/DocumentPreviewDialog.tsx` do nexarena. Achou
referência a eles num app → é resíduo, delete (imports mortos incluídos).

### Setup (projeto novo)

1. Invoque **`shadcn`** → `init`, depois `add sidebar dropdown-menu avatar` (**sem `breadcrumb`**: o `ui/breadcrumb.tsx` estava sem uso em 4 apps e foi apagado em 2026-10-01 — o título da página vem do header/`usePageHeader`, não de breadcrumb). Reconcilie o
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

Tela de entrada pública em `/`, que existe pra levar o visitante ao `/auth/login`. **Fora** da casca.
**Duas variantes válidas** (escolha por produto; a rota e o contrato de auth são os mesmos). A rota
`/auth/login` é o destino de ambas:

| Variante | Quando | Referência |
| --- | --- | --- |
| **Splash mínima** (esta parte, abaixo) | app interno/B2B fechado, sem aquisição por busca | `references/landing-route.tsx` |
| **Landing com seções** | produto que vende sozinho: hero → USP → demonstração/showcase → como funciona → confiança → FAQ → CTA final → rodapé | kailos `components/landing/*` (`landing-page.tsx` compõe `LandingNav/Hero/Usp/Assistant/Showcase/System/Origin/Trust/Faq/CallToAction/Footer`; CSS por bloco `landing*.css`; fontes de marca carregadas **só ali** via `<link precedence="default">` + `<title>`/`canonical` hoisted pelo React 19; app usa Geist empacotada) |

Landing com seções: continua **rota pública fora da casca** (`routes/index.tsx` → `<LandingPage/>`),
e o **CTA da nav muda por estado** — `isAuthenticated ? "Ir para o painel" → ROUTES.APP.DASHBOARD :
"Entrar" → ROUTES.AUTH.LOGIN`. O kailos **não redireciona** o logado para dentro (a landing é a
cara pública do site; ele chega ao app pelo botão). A splash mínima mantém o redirect de
autenticado (contrato abaixo). Direção visual de qualquer landing → `ui-ux-pro-max`.

### Splash mínima — full-screen, atmosférica, UM CTA

Estrutura/contrato aqui; **direção estética** (paleta, tipografia, motion) vem de `ui-ux-pro-max` —
comprometa-se com uma direção bold e específica.

### Contrato

| Regra | Detalhe |
| --- | --- |
| **Pública, sem casca** | `src/routes/index.tsx`, filho direto do `__root.tsx` puro. Sem sidebar/header. |
| **Redireciona autenticado** | `beforeLoad` → se `authStore.getState().isAuthenticated`, `throw redirect({ to: "/dashboard" })` (só splash; a landing com seções não redireciona). |
| **Um CTA** | Um único `<Button asChild>` envolvendo `<Link to="/auth/login">`. Sem ação secundária competindo. |
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
- **CTA** — `<Button size="lg" asChild>` + `<Link to="/auth/login">` + `ArrowRight` trailing.

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
4. Verifique: `/` full-screen sem casca; CTA chega no `/auth/login`; visitante autenticado é redirecionado (splash) ou vê "Ir para o painel" (landing com seções).

---

## References

- `references/app-sidebar.tsx` — template do `<AppSidebar>`.
- `references/useAuth.ts` — o composition hook.
- `references/migration.md` — aplicar a casca a projeto existente; migrar de auth Context (`DataProvider`).
- `references/landing-route.tsx` — template completo da rota de landing (splash mínima).
- Código vivo (kailos `frontend/src/`): `components/sidebar/org-selector.tsx`, `components/organizations/NewOrgDialog.tsx`,
  `stores/{organization,new-org-dialog}-store.ts`, `hooks/useAuth.ts` (`useCurrentOrgRoles`),
  `lib/auth/permissions.ts` (`hasOrgPermission`), `components/notifications/*`, `hooks/usePushSubscription.ts`,
  `public/{sw.js,manifest.json}`, `components/landing/*`.

> O layout (`SidebarLayout`/`SidebarChatLayout`, 1440, `fullBleed`) é do gate `frontend` →
> `references/layouts.tsx`. Não duplique aqui.
