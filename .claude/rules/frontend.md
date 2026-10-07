---
paths:
  - "frontend/**"
  - "config/nginx/**"
---

# Frontend — TypeScript, React, TanStack & Architecture

> Esta rule é o **O QUÊ** (invariante + proibido). O **PORQUÊ**, a assinatura do bug e o código
> canônico moram no skill `frontend` — a ref de cada linha. Invoque o skill ANTES de escrever UI.

## ⚠️ ANTES de construir/editar frontend (gate MUST)

**Consultar OBRIGATORIAMENTE o skill `frontend` (o PORTÃO) antes de qualquer Plan/construção de UI** —
checklist ordenado de invariantes + roteamento pros skills profundos (`react-19-patterns`, `shadcn`,
`tailwind-4-setup`, `ui-ux-pro-max`, `threejs-r3f-patterns`, `app-scaffold`,
`frontend-performance-audit`). Contrato em uma linha: **layout dita a largura** (página NUNCA seta
`max-w`) · sidebar app = **1440 centrado** · **zero Sheet lateral** (Dialog-first) · **grid p/ peers, 1
coluna contida p/ sequencial** · **responsivo por CSS, nunca `useIsMobile()`** · **mobile-first nunca
quebra**.

## Stack

| Layer        | Tool                         | Nota                                                                                                                                                                      |
| ------------ | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Language     | **TypeScript 7 (TSGo)**      | `@typescript/native-preview` quando disponível. `camelCase` em tudo; `snake_case` só no boundary da API.                                                                  |
| Pkg Manager  | **bun**                      | `bun add/dev/run`. NUNCA npm/yarn/pnpm.                                                                                                                                   |
| Runtime      | **React 19**                 | Functional, hooks, named exports. `use()`, `useActionState`, `useOptimistic`, `useFormStatus`, Form Actions, ref-as-prop, Context-as-Provider. Skill `react-19-patterns`. |
| Build        | **Vite 8 (Rolldown)**        | `@/` → `src/`. `VITE_*` em `app.yaml > vite:`.                                                                                                                            |
| Router       | **TanStack Router**          | File-based, `beforeLoad` para auth.                                                                                                                                       |
| Data         | **TanStack Query**           | TODA data fetching client-side. `useEffect + fetch` é PROIBIDO.                                                                                                           |
| Forms        | **TanStack Form + Zod 4**    | `validators: { onChange: zodSchema }`. NUNCA react-hook-form; `zod-form-adapter` é legado.                                                                                |
| Styling      | **Tailwind CSS 4**           | CSS-first config (sem `tailwind.config.ts`). Skill `tailwind-4-setup`.                                                                                                    |
| UI base      | **Shadcn/ui 4**              | Semantic CSS vars only. Skill `shadcn`.                                                                                                                                   |
| UI especial  | **Magic UI**                 | Animated List, Ticker, Marquee, Globe, Shimmer. Extende registry Shadcn.                                                                                                  |
| Charts       | **Shadcn Charts** (Recharts) | `ChartContainer` + `ChartConfig` + `ChartTooltip`. Skill `shadcn` (sub-rule `charts.md`).                                                                                 |
| Animation 2D | **Motion** (`motion`)        | NÃO `framer-motion`. CSS-first.                                                                                                                                           |
| Visual 3D    | **Three.js + R3F + drei**    | Skill `threejs-r3f-patterns`. Para visual "vivo" sem 3D, prefira Magic UI.                                                                                                |
| Icons        | **react-icons**              | Import por set p/ tree-shake: `import { LuSearch } from "react-icons/lu"`.                                                                                                |
| Input masks  | **react-imask**              | CPF, phone, dates.                                                                                                                                                        |

## Invariantes não negociáveis

Refs sem prefixo = `skills/frontend/references/`.

- **Componentes**: <200 ideal | 200–350 monitor | 350–500 split | 500+ proibido. Named exports. Typed props. `interface` para shapes, `type` para uniões. Sem `any` — `unknown` + type guard. `@/` absolute imports (NUNCA `../../../`).
- **React 19**: `ref` como prop (`forwardRef` LEGADO). `<MyContext value={...}>` (`.Provider` LEGADO). Metadata inline (sem `react-helmet`). Form async / fetch fora de Query / optimistic / `useEffect + fetch|setState` → skill `react-19-patterns`.
- **State**: 5 níveis (local/URL/server/UI/outside-react). TODA API data em TanStack Query (NUNCA duplicar em Context/store). Filtros/pagination em URL (`useSearch`). Context `value` SEMPRE `useMemo`. Ref `state-management.md`.
- **Responsivo = CSS, nunca JS**: toda troca desktop↔mobile (tabela↔card, abas↔`Select`, barra de filtros↔dialog) monta as DUAS formas e alterna com `md:hidden`/`max-md:hidden`. `useIsMobile()` resolve em `useEffect` → pisca no 1º frame e remonta a árvore. Estado de popover/overlay compartilhado entre as duas cópias é **por superfície** (`"inline" | "dialog"`), senão abre também o da cópia escondida.
- **Overlays**: Dialog-first (form, snippet, confirm, detalhe, picker); **ZERO Sheet lateral** (mobile nav/filtro → Dialog ou Drawer vaul). Overlay que merece F5/link (hub de settings, inspector) → deep-link via search param; 2+ itens de config na sidebar → um hub (`h-[85vh] lg:max-w-6xl`). Dialog-em-Dialog só hub→ação efêmera. **Saída**: `ConfirmDialog`/`AlertDialog` não tem X nem click-fora, então o par `Cancelar` + ação é OBRIGATÓRIO; qualquer outro Dialog/`FormDialog` tem X + click-fora e o footer leva SÓ a ação afirmativa (PROIBIDO botão cujo `onClick` só fecha — ação de negócio homônima como "Cancelar orçamento" fica). **Geometria na BASE do `DialogContent`**, nunca no call site: `max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] overflow-y-auto overscroll-contain` + trava `max-md:max-h-[calc(100svh-3rem)] max-md:max-w-[calc(100%-2rem)]` (lightbox full-bleed é opt-in `max-md:max-h-none max-md:max-w-none`). Refs `overlays.md`, `settings-dialog.md`.
- **Form dialogs & teclado mobile**: overlay com `<input>`/`<textarea>`/`<select>` = `FormDialog` (`ui/form-dialog.tsx`), NUNCA `DialogContent` cru. Ancorado na `visualViewport` (`--vv-offset-top`/`--vv-height`); 3 faixas — header `shrink-0` / corpo `min-h-0 flex-1 overflow-y-auto overscroll-contain` / footer `shrink-0` com safe-area; `compactStyle` zera `transform` **E** `translate`; `size` `sm|md|lg|xl`. `index.html` com `viewport-fit=cover, interactive-widget=resizes-content` + compensações de safe-area no mesmo commit. PROIBIDO: `max-h-[Nvh]`/`h-[Nvh]` em dialog de form · `overflow-y-auto` no `className` do `FormDialog` · `autoFocus` no 1º input · `scrollIntoView` no campo focado · Drawer/vaul como "solução de teclado". Refs `mobile-keyboard.md`, `form-dialog.tsx`.
- **Campo nativo ≥16px no celular**: todo input/textarea/select de `components/ui/` é `text-base … md:text-sm` (root 17px → `text-sm` = 14.875px → auto-zoom do iOS leva o dialog pra fora da tela); campo que herda fonte de wrapper leva a classe no próprio input. PROIBIDO `maximum-scale=1`/`user-scalable=no` e `input { font-size: 16px !important }`. Ref `mobile-keyboard.md`.
- **Primitivas shadcn v4**: `<Label>` sem `select-none` (só superfície clicável inteira — `ToggleCard`/`CardCheckbox` — é não-selecionável). `Card` = raiz `flex flex-col gap-6 py-6`, slots só `px-6`: PROIBIDO `p-*`/`py-*`/`pt-*`/`pb-*` em `CardContent`/`CardHeader`/`CardFooter` e `space-y-*` em `CardHeader`; compacto = `<Card className="gap-4 py-4">` + slots `px-4`. Ref `shadcn-v4-primitives.md`.
- **Abas**: `TabsList` com 3+ triggers vira `Select` abaixo de 768px, automático (call site escreve `<TabsList>` puro); `Tabs` dirige o Radix com o espelho (`value={current}`), nunca com `defaultValue`. Escapes: `mobile="strip"` (ícone-only/1 palavra) e `selectClassName` (lista dividindo linha com vizinho). **Seções por rota** (tira de 3+ `<Button asChild><Link>`) = mesma regra: `Select` que navega `md:hidden` + `<nav>` `max-md:hidden`, um array só. PROIBIDO: `isMobile ? <Select> : <TabsList>` · `overflow-x-auto` na tira · duplicar a fonte de verdade das abas. Refs `responsive-tabs.md`, `tabs.tsx`.
- **Listas**: coleção = `ListToolbar` (busca debounce 300ms/mín. 3 chars + filtros + ordenação, tudo na **URL** via `validateSearch`) → `DataList` (UMA definição de coluna: `<table>` ≥768px, card abaixo) → `useInfiniteList` (10 por página, sentinela + `<Button>Carregar mais</Button>`). Conjunto bounded (itens de orçamento, parcelas, ranking) → `StaticDataList`; a pergunta é "o nº de linhas cresce com o uso?". **Toolbar em UMA linha**: busca + filtros + ordenação no topo à **esquerda**, ações à **direita**; filtro é controle de UMA altura (rótulo dentro via `InputGroupAddon`/valor "Todos os X", nunca `<Label>` empilhado); no celular busca full-width + `[Filtros][ações]`. Barra de filtros de dashboard segue o mesmo desenho (celular: botão "Filtros" → `FormDialog`). Query key `[endpoint, "list", "infinite", params]`. PROIBIDO: paginação por número de página · `limit: 100..500` · `<Table>` sem card no mobile · filtro/sort/busca em `useState` · ação **abaixo** da lista · filtro/ordenação numa 2ª linha embaixo das ações · toolbar ad-hoc · dep não-vazia no `useEffect` do sentinel. Refs `list-screen.md`, `data-list.tsx`, `list-toolbar.tsx`, `use-infinite-list.ts`.
- **Confirmações**: destrutiva SEMPRE `ui/confirm-dialog.tsx` (AlertDialog central; `busy` = pending da mutation, parent fecha no `onSuccess`; em lista um único `ConfirmDialog` no container). PROIBIDO: tira inline/accordion · button-swap · `window.confirm` · AlertDialog ad-hoc. Ref `overlays.md`.
- **Toggles**: on/off com rótulo → `ToggleCard` (Switch-in-card PROIBIDO; pending em `busy`, nunca `disabled`); peers `size="compact"` em grid, único em grupo contido; multi-select → `CardCheckbox`; Switch inline só em célula de tabela densa. Ref `toggle-card.md`.
- **Uploads & Mídia**: dropzone no vazio; cheio = o asset é o trigger do menu (visualizar/copiar/baixar/substituir/excluir); `useFileUpload` validator-only + `UploadError.fromUnknown` + `file-types`; preview `DocumentPreviewDialog`; delete via `ConfirmDialog`. Backend → gate `uploads-storage`. Ref `file-upload.md`.
- **Permissões/RBAC**: NUNCA nuvem plana de badges — `PermissionGroupList` por domínio com badge por VERBO (cor/ícone/ordem canônicos de `permissionVerbs.ts`; verbo novo entra na mesma PR). A aba de conceder usa o MESMO `groupPermissions(keys, catalog)`; busca obrigatória por aba (local, NFD+lower); superusuário vê o catálogo inteiro com banner de bypass; arquivo compartilhado NUNCA tem chave de papel nem campo de projeto (`GrantLock`); dialog de abas = tamanho único. Ref `permissions-display.md`.
- **FK em forms**: `EntityPicker` (busca server-side `?search=`, `limit` 10 crescendo de 10 em 10, trigger `FIELD_TRIGGER_CLASS`, quick-create "Novo…" cujo `onSaved` chama `onChange`); wrapper fino por entidade. PROIBIDO `Select` estático p/ lista que cresce · `Input` de ID/UUID. `Select` só p/ lista bounded administrativa. Backend: o mesmo list endpoint paginado, sem `COUNT(*) OVER()`. Ref `entity-picker.md`.
- **Layout**: página NUNCA seta `max-w`. `SidebarLayout` = `max-w-[1440px]` centrado + gutter `px-[clamp(1rem,2vw,2rem)] py-4 md:py-6` (o mesmo no header) · `SidebarChatLayout` = full-bleed com sidebar intacta · `AuthLayout` = card central. Página→Abas→Dialogs; grid p/ peers, 1 coluna contida p/ sequencial (datas, logo→banner). PADRÃO (layout/largura/overlay/`react-icons`/`font-size 17px`) ≠ IDENTIDADE (font-family/cores/estilo shadcn, por projeto). Refs `layouts.tsx`, `grid-vs-stack.md`.
- **Auth**: access em memória (NUNCA storage/persist); refresh on 401 via `withRefreshLock` disputado por TODO caller, guard = snapshot do token PRÉ-lock (nunca "já existe token"); cookie HttpOnly path-scopado SameSite=Strict; router só monta depois do bootstrap decidir a sessão; resume de background revalida e **só 401/403 encerram a sessão** (rede/5xx nunca desloga); login = reset total (limpa access + `queryClient.clear()` + revoga a sessão anterior, best-effort). Gate `auth` (`auth-hardened.md`, `google-login.md`).
- **PWA**: manifest `display: minimal-ui` com `name`/`short_name`/`scope`/`theme_color` reais + ícone maskable; botão de recarregar só em standalone + pull-to-refresh com `invalidateQueries` (nunca `location.reload()`); `viewport-fit=cover` + safe-area + `overscroll-behavior-y: contain` (sempre junto do pull-to-refresh ligado no `<main>`); item "Instalar app" SÓ no menu do usuário da sidebar (nunca login/landing), `sw.js` push-only registrado no boot. Ref `pwa-mobile.md` §6.
- **Performance**: polling em leaf memoizado (nunca route component); Context `value` em `useMemo`; heavy children `React.memo` + props estáveis; charts mount==unmount. Budget: route load ≤15 renders, polling tick ≤2. Ref `performance-preventivo.md`; regressão em prod → skill `frontend-performance-audit`.
- **Tailwind 4**: CSS-first (`@import "tailwindcss"` + `@theme inline` OKLCH). Breakpoints de viewport p/ página e grid; `@container` só p/ componente reusável em slot de largura variável. Vars semânticas (`bg-background`), NUNCA cor crua. Skill `tailwind-4-setup`.
- **Code blocks**: `<pre>`/`<code>` com `whitespace-pre-wrap break-all`, NUNCA `overflow-x-auto` (vertical ok).
- **CSP**: todo host externo novo = linha em `config/nginx/snippets/security-headers-base.conf` **no MESMO commit**, na diretiva certa (`fetch`→`connect-src` · `<script>`→`script-src` · `<iframe>`→`frame-src` · `<audio>/<video>`→`media-src` · `<img>`→`img-src`). SDK de terceiro costuma pedir 2–3 diretivas; diretiva declarada NÃO herda de `default-src` (inclua `'self'`). `fetch` de URL da própria página (`blob:` do `createObjectURL`, data URL montada no submit) também passa por `connect-src` — `blob:` em `img-src` cobre o preview, não o envio. Sintoma de esquecer: a tela não quebra, só não salva — o erro fica no console do usuário. Ref `api-and-csp.md`.
- **DateTime**: API entrega ISO 8601 com `Z`. NUNCA offset math manual. Display via `Intl.DateTimeFormat` em utility module (`formatDateTime`, `formatDate`). Null/invalid → `"—"`.

## TanStack Router

- Auth em `beforeLoad` ONLY (zero flash). `throw redirect(...)`.
- **`beforeLoad` é SÍNCRONO** — lê `authStore.getState()` e decide. Zero `await`, zero fetch, zero espera por bootstrap (`waitForAuthCheck`/polling com deadline vira redirect falso em 3G).
- `defaultPreloadStaleTime: 60_000` mínimo (`0` = request storm em hover).
- Stores (`organizationStore`, `authStore`) lidos dentro de `beforeLoad` (fora do React).

## API Layer

- `camelCase` ↔ `snake_case` no `ApiClient` ONLY. Components/hooks sempre `camelCase`.
- `client.get<T>()` → `ApiResponse<T>`: `{ data, status, success }`.
- Lists → `PagedResponse<T>`: `{ items, total, skip, limit, hasMore? }` (`hasMore` opcional só na migração — fallback `skip + items.length < total`).
- Adapter (baseURL+headers) → ApiClient (fetch+key rename) → Query function (extrai `res.data`) → `useCrud` (paged pattern).
- **`fetch` cru SÓ para API externa** (BrasilAPI, IBGE, ViaCEP). Endpoint próprio passa pelo `ApiClient` — inclusive `getBlob`/`getRaw` — senão não há refresh em 401.
- **Falha de rede = UMA mensagem pt-BR** (`lib/api/network-error.ts`) aplicada no adapter E no `ApiClient`; detecção `error instanceof TypeError`, NUNCA por texto ("Load failed" no iOS). Ref `api-and-csp.md`.

## Naming

Components `PascalCase` | Hooks `usePrefix` | Stores `kebab-store` | Types `PascalCase` | Constants `UPPER_CASE` | Routes `kebab-case`/`$param`. UI strings em pt-BR. `ROUTE_PATHS` constants para todas as rotas.

## Formatter (Prettier) — CRITICAL FOR EDIT TOOLS

2-space indent (spaces only) | double quotes | 100 char line length | semicolons | trailing commas (es5)
