---
name: frontend
description: PORTÃO obrigatório antes de QUALQUER construção/edição de UI em React 19 + TanStack + Tailwind 4 + shadcn. Checklist ordenado de invariantes que você verifica e marca um a um — layout dita a largura (página NUNCA seta max-w; sidebar app capado em 1440 centrado; Página→Abas→Dialogs), overlays Dialog-first com ZERO Sheet lateral, grid para itens paralelos / 1-coluna contida para conteúdo sequencial (datas dependentes, logo→banner empilhado), onde mora cada state (local/URL/server/contexto/zustand), idiomas React 19, checklist preventivo de performance, vars semânticas do Tailwind, uso semântico do shadcn, FK em forms via EntityPicker (combobox de entidade pesquisável no servidor + quick-create "Novo…"; Select estático p/ lista que cresce e Input de ID cru são PROIBIDOS), form dialog via FormDialog ancorado na visual viewport (teclado do celular escondendo campo/botão de salvar, dialog comprido no mobile, safe-area/notch, meta viewport, PWA standalone — `dvh` NÃO resolve isso no iOS), tela de lista via ListToolbar+DataList (tabela no desktop vira card no mobile, scroll infinito de 10 em 10, busca com debounce, filtros e ordenação na URL; paginação por número de página é PROIBIDA), abas que não cabem no celular (TabsList com 3+ abas vira Select abaixo de 768px, automático e por CSS), dialog que sai pra cima/pra esquerda da tela no mobile (geometria à prova de viewport na base do DialogContent), barra estética mínima (sem cara genérica de IA; identidade é por-projeto), mobile-first como gate bloqueante, PWA instalado na tela de início (manifest `minimal-ui`, botão de reload obrigatório porque o app instalado não tem F5, pull-to-refresh, safe-area/notch, metas apple-\*). Distingue PADRÃO (cross-projeto) de IDENTIDADE (font-family/cores/estilo shadcn, por-projeto). Roteia para os skills profundos (react-19-patterns, shadcn, tailwind-4-setup, ui-ux-pro-max, threejs-r3f-patterns, app-scaffold, frontend-performance-audit). INVOCAR ANTES de criar/editar qualquer layout, página, componente, overlay, grid, form, tabela/lista/CRUD, dialog, upload de mídia, ou casca de app — e no MODO AUDITORIA quando o pedido é varrer/consertar a consistência de UI de um projeto (larguras divergentes entre abas, chat que buga/abre fullscreen, Sheet lateral, logo gigante + banner minúsculo, quebra no mobile, teclado do celular cobrindo o formulário, tabela ilegível no celular, lista sem filtro/ordenação).
---

# Frontend — O Portão

Ponto de entrada único de frontend (é o que o gate MUST do `frontend.md` exige). **NUNCA construa
UI sem passar por aqui.** Dois modos:

- **Modo 1 — Checklist de build:** antes de escrever/editar UI, passe por cada item EM ORDEM e marque.
  Cada item carrega a regra; o `deep:` aponta o detalhe completo só quando você precisar do "como".
- **Modo 2 — Auditoria & Fix:** runbook para varrer e consertar a divergência de um projeto numa
  sessão limpa.

Os build-invariants vivem aqui (em `references/`). Os skills profundos com gatilho próprio ficam
standalone e são linkados no roteamento (fim do arquivo).

---

## Modo 1 — Checklist de build (em ordem; marque cada quesito)

- [ ] **1. Layout & largura.** O layout dita a largura — a página **NUNCA** seta `max-w` próprio.
  Layouts nomeados donos do macro UI/UX: `AuthLayout` (card central) · `SidebarLayout` (conteúdo
  **`max-w-[1440px]` centrado** + padding `px-4 py-4 md:px-6 md:py-6`) · `SidebarChatLayout`
  (full-bleed, sidebar/header intactos, header também full-bleed). Complexidade → **Página → Abas →
  Dialogs**, nunca largura/layout novo por página. A escolha de qual rota usa qual layout fica em UM
  lugar (constante no `_authenticated.tsx`). *deep: `references/layouts.tsx`.*
- [ ] **2. Overlays.** Dialog-first para tudo (form, detalhe, confirm, picker). **ZERO Sheet lateral
  no app.** Mobile nav/filtro → Dialog ou Drawer (vaul). Tamanho por necessidade; a **geometria** é
  da base do `DialogContent` (`max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] overflow-y-auto` — capa
  a altura e contém os DOIS eixos; sem isso o dialog alto sai pela borda de cima, fora do alcance de
  qualquer scroll, e o conteúdo largo faz a página inteira panar) **+ a trava
  `max-md:max-h-[calc(100svh-3rem)] max-md:max-w-[calc(100%-2rem)]`**, que impede o call site de vazar
  medida de desktop (`max-h-[85vh]`, `max-w-4xl`) pro celular — no iOS `vh` é a viewport GRANDE.
  Campo nativo dentro do overlay vai a **`text-base` no celular** (< 16px = auto-zoom do iOS, que pana
  a visual viewport e leva o dialog pra fora da tela). Overlay bookmarkável (hub de settings, inspector) →
  **deep-link via search param**; 2+ itens de config na sidebar → consolidar no hub. Confirmação
  destrutiva → **`ConfirmDialog`** central (NUNCA tira inline/accordion/button-swap/`window.confirm`).
  *deep: `references/overlays.md` + `references/settings-dialog.md` + `references/confirm-dialog.tsx`.*
- [ ] **3. Grid vs Stack.** Itens paralelos/peers → **grid** (`grid-cols-1 sm:grid-cols-2
  lg:grid-cols-3`). Conteúdo sequencial/dependente (datas início→fim, logo→banner, passos) → **1
  coluna mesmo no desktop**, com a largura do GRUPO contida (`max-w-2xl` no fieldgroup, nunca na
  página). Logo+banner = empilhado full-width (nunca `sm:grid-cols-2`). *deep: `references/grid-vs-stack.md`.*
- [ ] **4. State placement.** 5 níveis: local (`useState`) · URL (`useSearch` p/ filtros/pagination/
  tab) · server (TanStack Query p/ TODA API data — NUNCA duplicar em store/Context) · deep UI
  (Context com `value` memoizado) · outside React (Zustand p/ token/orgId lidos fora de hook). *deep:
  `references/state-management.md`.*
- [ ] **5. React 19 idioms.** `use()`/`useActionState`/`useOptimistic`/Form Actions; `ref` como prop
  (sem `forwardRef`); `<Context value>` (sem `.Provider`); metadata inline. **NUNCA `useEffect +
  fetch`** (é TanStack Query) nem `useEffect + setState` p/ derived (é `useMemo`). *deep: skill
  `react-19-patterns`.*
- [ ] **6. Performance preventivo.** Context `value` em `useMemo`; polling/`setInterval` em leaf
  memoizado (nunca route component); heavy children com `React.memo` + props estáveis; sem `index`
  como key. Render budget: route load ≤15, polling tick ≤2. *deep: `references/performance-preventivo.md`
  (regressão já em prod → skill `frontend-performance-audit`).*
- [ ] **7. Tailwind semantic vars.** Cores via vars shadcn (`bg-background`, `text-muted-foreground`),
  **NUNCA hex cru**. CSS-first (`@theme inline`, OKLCH). *deep: skill `tailwind-4-setup`.*
- [ ] **8. shadcn semantic.** Use os componentes shadcn como base; semantic CSS vars only; composição
  correta (forms, inputs, variants). *deep: skill `shadcn`.*
- [ ] **8a. Toggles — Switch-in-card PROIBIDO.** Qualquer on/off com rótulo visível → **`ToggleCard`**
  (`ui/toggle-card.tsx`: card todo clicável, chip Ativo/Desativado, liquid wash + hairline border
  beam sincronizado, CSS-only). Peers em grid `size="compact"`; único → grupo contido (`max-w-lg` no
  fieldgroup). Switch inline residual
  SÓ em célula de tabela densa. Multi-select → `CardCheckbox`. *deep: `references/toggle-card.md` +
  `references/toggle-card.tsx` (canônico).*
- [ ] **8b. Permissões/RBAC — nuvem de badges PROIBIDA.** Lista de permissões → **agrupada por
  domínio** (linha a linha: header pt-BR + count) com badges por VERBO (cor/ícone/ordem canônicos:
  read=sky/Eye, create=emerald/Plus, update=amber/Pencil, delete=rose/Trash2,
  manage=violet/Settings2…). Metadata (`group`/`group_pt`/`order`) mora no catálogo Pydantic;
  componente `PermissionGroupList`. Dialog de tabs = tamanho ÚNICO fixo (nunca `max-w` por aba).
  *deep: `references/permissions-display.md`.*
- [ ] **8c. Uploads & Mídia.** Upload de arquivo/imagem → **dropzone** (clique/arraste) no vazio;
  cheio = asset/card é o trigger do menu (visualizar/copiar/baixar/substituir/excluir, sem
  three-dots). Validação `useFileUpload` (validator-only) + erros pt-BR `UploadError` + ícones
  `file-types`. Dois fluxos de título (slot predefinido vs captura inline). Preview
  `DocumentPreviewDialog`; delete via `ConfirmDialog`. Componentes apresentacionais (callbacks); dados
  por projeto. Backend → gate `uploads-storage`. *deep: `references/file-upload.md`.*
- [ ] **8d. FK / seleção de entidade relacionada.** Campo de FK em form → **`EntityPicker`**
  (`ui/entity-picker.tsx`: Popover+Command `shouldFilter={false}`, busca **server-side** `?search=`
  com `limit: 20` e `enabled` só com popover aberto, CTA "Novo…" que abre o `*FormDialog` da
  entidade e auto-seleciona no `onSaved`). **PROIBIDO**: `Select` estático p/ lista que cresce com
  uso; `Input` de ID/UUID cru. `Select` residual SÓ p/ lista bounded administrativa (membros da
  org, roles, enums); seletor de contexto global (trocar org ativa) segue `DropdownMenu`. Backend:
  o MESMO list endpoint paginado (`PagedResponse` + `search` ILIKE), sem endpoint de autocomplete.
  *deep: `references/entity-picker.md` + `references/entity-picker.tsx` (canônico).*
- [ ] **8e. Form dialog & teclado mobile — `DialogContent` cru é PROIBIDO em dialog com input.**
  Qualquer dialog com campo de formulário → **`FormDialog`** (`ui/form-dialog.tsx`: header fixo /
  corpo rolável / footer fixo, ancorado na **visual viewport** no mobile). No iOS o teclado **não**
  encolhe a layout viewport — `100vh`/`100dvh`/`svh` não mudam, e o WebKit ainda desloca a área
  visível (`visualViewport.offsetTop > 0`) com o body travado pelo Radix, jogando o `DialogContent`
  (`position: fixed`) pra fora pelo topo. `max-h-[85vh] overflow-y-auto` é o padrão ANTIGO e não
  resolve. Sem `autoFocus` no primeiro input; sem `overflow-y-auto` residual no `className`. Meta
  viewport com `viewport-fit=cover` + `interactive-widget=resizes-content`, e as compensações de
  safe-area junto. *deep: `references/mobile-keyboard.md` + `references/form-dialog.tsx` (canônico).*
- [ ] **8f. Tela de lista — tabela no PC vira card no mobile.** Lista de registros → **`ListToolbar`
  + `DataList`** (`ui/list-toolbar.tsx`, `ui/data-list.tsx`, `hooks/useInfiniteList.ts`): UMA
  definição de coluna renderiza a tabela (≥768px) e a pilha de cards (<768px); **scroll infinito de
  10 em 10**; busca com debounce + mínimo 3 chars; filtros e ordenação. **Paginação por número de
  página é PROIBIDA.** `q`/`status`/`sort`/`order` na URL (`validateSearch`) — nunca `useState`.
  Nada abaixo da lista (o fim da página nunca chega). Backend: gate `database`
  (→ `list-pagination.md`). *deep: `references/list-screen.md` + `references/data-list.tsx` +
  `references/list-toolbar.tsx` + `references/use-infinite-list.ts` (canônicos).*
- [ ] **8g. Abas no mobile — 3+ abas viram `Select`.** `TabsList` com 3+ triggers renderiza um
  `Select` abaixo de 768px, **automaticamente** (o componente conta os filhos; call site escreve
  `<TabsList>` puro). A troca é CSS (`md:hidden` / `max-md:hidden`) com as duas formas montadas —
  **NUNCA `useIsMobile()`**, que resolve em `useEffect` e pisca + remonta o painel ativo. Escapes:
  `mobile="strip"` (aba ícone-only / rótulo de 1 palavra) e `selectClassName` (quando a lista divide
  linha flex com um vizinho). **PROIBIDO** `isMobile ? <Select…> : <TabsList…>` no call site — é
  exatamente o que o componente substitui. *deep: `references/responsive-tabs.md` +
  `references/tabs.tsx` (canônico).*
- [ ] **9. Barra estética mínima.** Sem cara genérica de IA (nada de gradiente roxo + Inter + layout
  template); hierarquia/contraste/espaçamento; respeitar a identidade do projeto. *deep:
  `references/design-bar.md` (+ skill `ui-ux-pro-max` p/ paleta/fonte/estilo).*
- [ ] **10. Mobile-first (gate bloqueante).** Default 1 coluna; escala `sm/md/lg/xl`. Antes de polir
  desktop, garanta em **375px**: sem scroll horizontal, 1 coluna, touch ≥44px, chat preenche altura
  (`flex-1 min-h-0`, nunca `h-[calc(100dvh-Xrem)]` mágico), **tabela virou card** (8f) e **o teclado
  não esconde campo nem o botão de salvar** (8e). Mobile quebrado **bloqueia** o merge.
- [ ] **10a. PWA / instalado na tela de início.** App instalado não tem F5 nem barra de endereço →
  `manifest.json` com `display: "minimal-ui"` (o iOS ignora e abre standalone assim mesmo), `scope`,
  `name`/`short_name`/`theme_color` **reais** (placeholder do scaffold é o nome no celular do
  usuário) e ícone `maskable`; **afordância de recarga in-app obrigatória** — botão só quando
  instalado (`display-mode` + `navigator.standalone`) e pull-to-refresh próprio, ambos chamando
  `queryClient.invalidateQueries()` (**nunca `location.reload()`**, que descarta o bundle e o access
  em memória); metas `apple-mobile-web-app-*` + `apple-touch-icon`; `overscroll-behavior-y: contain`.
  Service worker só com pedido explícito. *deep: `references/pwa-mobile.md`.*
- [ ] **11. PADRÃO vs IDENTIDADE.** Padroniza (cross-projeto): layout, larguras (1440), enquadramento,
  overlays, grid-vs-stack, mobile-first, `react-icons`, `html { font-size: 17px }`. **NÃO** padroniza
  (por-projeto): font-**family**, **cores**, **estilo shadcn** (baseColor/new-york etc.). Nunca
  "unifique" marca entre apps.

### Ícones
`react-icons` para ícones de app — import nomeado por set p/ tree-shake (`import { LuSearch } from
"react-icons/lu"`). Primitivos shadcn mantêm o icon lib vendored deles (não mexer).

---

## Modo 2 — Auditoria & Fix (sweep em sessão limpa)

Quando o pedido é varrer/consertar a consistência de UM projeto ("padroniza o app", "as abas têm
larguras diferentes", "o chat buga", "o logo tá gigante"). Roda inline (single-agent).

### Passo 1 — Inventário (grep)

```bash
rg -n "max-w-\[?\d|max-w-(5xl|6xl|7xl|2xl|3xl|4xl)" frontend/src/routes frontend/src/components --glob '!**/ui/**'
rg -n "Sheet(Content|Trigger)?\b" frontend/src --glob '!**/ui/sidebar.tsx'
rg -n "h-\[calc\(100dvh" frontend/src
rg -n "grid-cols-2" frontend/src/components  # candidatos a logo+banner / datas
rg -n "<Switch" frontend/src --glob '!**/ui/**'  # Switch-in-card → ToggleCard
rg -n "permissions.map|permission.*Badge" frontend/src/components  # nuvem de badges → PermissionGroupList
rg -n "SelectTrigger" frontend/src/components frontend/src/routes --glob '!**/ui/**'  # Select de FK que cresce → EntityPicker
rg -n 'placeholder=".*(ID|UUID|[Ii]dentificador)' frontend/src  # Input de ID cru → EntityPicker
rg -n "useSidebarAutoCollapse|FULL_BLEED|isFullBleed|variant=\"full\"" frontend/src
rg -n "font-size" frontend/src/index.css
rg -ln "DialogContent" frontend/src/components --glob '!**/ui/**'   # form dialog cru → FormDialog
rg -n "max-h-\[8[05]vh\]|h-\[9[02]vh\]" frontend/src               # altura estática → FormDialog
rg -n "autoFocus" frontend/src/components                          # 2ª fonte de foco no mobile
rg -n "transform|translate" frontend/src/components/ui/form-dialog.tsx  # compactStyle zera AS DUAS?
rg -n "max-h-|overflow-y|max-md:" frontend/src/components/ui/dialog.tsx  # base: 2 eixos + trava max-md:
rg -n "text-(xs|sm)" frontend/src/components/ui/{input,textarea,command,input-group,combobox}.tsx  # campo < 16px → auto-zoom iOS
rg -n "isMobile \?" frontend/src --glob '!**/ui/sidebar.tsx'       # tabs/tabela com switch em JS → CSS
rg -n "<TabsList" frontend/src --glob '!**/ui/**'                  # abas cobertas pelo dual-render?
rg -n "<Table" frontend/src/routes frontend/src/components         # tabela sem card no mobile
rg -n "hidden (sm|md|lg):table-cell" frontend/src                  # column-collapse virou card?
rg -n "page: *number|lastPage|Anterior|Próxima" frontend/src/routes # paginação por página → infinito
rg -n "limit: *[1-9]\d{2,}" frontend/src                           # fetch-all disfarçado
rg -n "viewport" frontend/index.html                               # viewport-fit + interactive-widget
rg -n '"display"|"short_name"|TanStack App' frontend/public/manifest.json  # standalone sem reload / nome de scaffold
rg -n "location.reload\(\)" frontend/src                           # reload que descarta bundle + access
```

### Passo 2 — Punch-list (por achado)

- [ ] **Página seta `max-w` próprio?** → remover; a largura é do layout.
- [ ] **Layout do chat com altura mágica** (`h-[calc(100dvh-...)]`)? → trocar por `flex-1 min-h-0`.
- [ ] **Sidebar auto-colapsa no chat** (`useSidebarAutoCollapse`)? → remover; sidebar fica normal.
- [ ] **Sheet lateral** (fora de `ui/sidebar.tsx`)? → Dialog (detalhe/confirm/form) ou Drawer vaul
      (filtro/nav mobile).
- [ ] **Logo+Banner em colunas iguais** (`sm:grid-cols-2`)? → empilhar full-width.
- [ ] **Conteúdo sequencial em grid** (datas dependentes lado a lado)? → 1 coluna contida.
- [ ] **Switch dentro de card/row com rótulo** (fora de célula de tabela densa)? → `ToggleCard`
      (`references/toggle-card.md`).
- [ ] **Nuvem plana de badges de permissões** (Dialog info, Efetivas)? → `PermissionGroupList`
      agrupado por domínio (`references/permissions-display.md`).
- [ ] **Select estático ou Input de ID/UUID cru para FK que cresce com uso** (cliente, veículo,
      contato…)? → `EntityPicker` + quick-create (`references/entity-picker.md`). Lista bounded
      administrativa (membros/roles/enums) fica em Select — decisão consciente, não pendência.
- [ ] **Shell em largura diferente de 1440**? → padronizar `max-w-[1440px]` + padding.
- [ ] **Header do chat capado em 1440** enquanto o conteúdo é full-bleed? → header full-bleed também.
- [ ] **`font-size` base ausente/divergente**? → `html { font-size: 17px }`.
- [ ] **Dialog com campo de input usando `DialogContent` cru / `max-h-[85vh]` / `h-[90vh]`**? →
      `FormDialog` (`references/mobile-keyboard.md`). Remover `autoFocus` do primeiro input e qualquer
      `overflow-y-auto` residual no `className`.
- [ ] **Base do `DialogContent` sem `max-h`/`overflow-y`**? → adicionar
      `max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] overflow-y-auto overscroll-contain` (e trocar o
      `w-full` da base pelo `w-[...]`). Sintoma: dialog alto sai pela borda de cima no celular e o
      conteúdo interno fica inalcançável (`references/overlays.md`).
- [ ] **`compactStyle` do `FormDialog` com `transform: "none"` mas sem `translate: "none"`**? →
      adicionar as duas. No Tailwind 4 o `-translate-x-1/2`/`-translate-y-1/2` da base do
      `DialogContent` sai pela propriedade **autônoma `translate`**, independente de `transform`.
      Sobrando, o full-bleed anda meia largura pra esquerda e meia altura pra cima e some da tela —
      só no celular. Assinatura: borda direita do dialog em ~50% da largura do aparelho e altura
      visível ~50% da tela (`references/mobile-keyboard.md`).
- [ ] **Base do `DialogContent` sem a trava `max-md:`**? → adicionar
      `max-md:max-h-[calc(100svh-3rem)] max-md:max-w-[calc(100%-2rem)]`. Sem ela cada `max-h-[85vh]`/
      `max-w-4xl` de call site — medida de desktop, e no iOS `vh` é a viewport GRANDE — vaza pro
      telefone; a variante não funde com a classe crua do call site, então no celular vence
      (`references/overlays.md`).
- [ ] **Campo nativo com fonte < 16px no celular** (`text-sm`/`text-xs` em `input.tsx`, `textarea.tsx`,
      `CommandInput`, `*ChipsInput`)? → `text-base … md:text-sm`. Com root de 17px, `text-sm` = 14.875px
      e o iOS dá auto-zoom ao focar: a visual viewport pana e o dialog `position: fixed` some pra cima/
      pra esquerda. Só acontece no celular (`references/mobile-keyboard.md`).
- [ ] **`isMobile ? <Select…> : <TabsList…>` num call site**? → apagar o ramo mobile, deixar
      `<TabsList>` puro; o componente faz o dual-render por CSS (`references/responsive-tabs.md`).
      Remover `useIsMobile` e os imports de `Select*` órfãos.
- [ ] **Meta viewport sem `viewport-fit=cover` + `interactive-widget=resizes-content`**? → padronizar
      **junto** com as compensações de safe-area (padding no shell, offset do Toaster, `fixed inset-0`).
- [ ] **`<Table>` sem card abaixo de 768px**? → `DataList` (`references/list-screen.md`).
      Column-collapse (`hidden lg:table-cell`) fica, mas só pra densidade acima de 768px.
- [ ] **Paginação por número de página / `limit: 100..500` fetch-all**? → `useInfiniteList` 10 em 10.
- [ ] **Lista sem busca, sem filtro de status ou sem ordenação**? → `ListToolbar` + `makeSortOptions`.
- [ ] **Filtro/busca/sort em `useState`**? → URL (`validateSearch`). Só o draft do input é local.
- [ ] **Botão de criar ou qualquer ação ABAIXO da lista**? → subir pro `ListToolbar` (com scroll
      infinito o fim da página nunca chega).
- [ ] **Manifest com `display: standalone`, nome de scaffold, sem `scope`/maskable — ou app instalado
      sem botão de reload**? → `references/pwa-mobile.md` (`minimal-ui` + afordância in-app; o usuário
      no iOS não tem como recarregar).
- [ ] **Quebra no mobile 375px**? → corrigir.

### Passo 3 — Fixes (receitas)

**Layouts** → adotar `references/layouts.tsx`: `SidebarShell` interno (com flag `fullBleed` p/ o
header) + `SidebarLayout` (1440) + `SidebarChatLayout` (full-bleed). Escolha por rota numa constante
no `_authenticated.tsx`.

**Chat height** (antes → depois):

```tsx
// ANTES (quebra quando header muda de altura / sidebar colapsa)
<div className="flex h-[calc(100dvh-2.5rem)] w-full flex-col overflow-hidden">
// DEPOIS (participa da cadeia flex do SidebarChatLayout)
<div className="flex min-h-0 w-full flex-1 flex-col overflow-hidden">
```

**Sheet → Dialog**: trocar `Sheet/SheetContent/SheetHeader/SheetTitle` por
`Dialog/DialogContent/DialogHeader/DialogTitle`, `side="..."` sai, adicionar `sm:max-w-md max-h-[85vh]
overflow-y-auto` conforme `references/overlays.md`.

**Página com max-w próprio**: remover o `mx-auto max-w-*` do wrapper — o layout já centra/capa em 1440.

### Passo 4 — Verificação

`bun dev` (ou build): páginas do mesmo layout com largura idêntica; chat preenche a área sem bug, com
sidebar e header alinhados; logo+banner empilhados; nenhum Sheet lateral; mobile 375px em 1 coluna sem
scroll horizontal. NÃO rode o `check.sh` da raiz se houver workflow ativo.

---

## Roteamento — abra o skill profundo quando…

| Quando                                                          | Skill                          |
| --------------------------------------------------------------- | ------------------------------ |
| Escrever/refatorar form async, optimistic, `use()`, ref-as-prop | `react-19-patterns`            |
| Adicionar/consertar/estilizar componente, charts, registry      | `shadcn`                       |
| Bootstrap do Tailwind, novos tokens/tema OKLCH                   | `tailwind-4-setup`             |
| Escolher paleta/fonte/estilo/direção estética de marca          | `ui-ux-pro-max`                |
| Cena 3D / shader / R3F                                          | `threejs-r3f-patterns`         |
| Montar casca de app autenticada (sidebar/auth/rotas) ou landing | `app-scaffold`                 |
| "Fica lento depois de X min" / "preciso dar F5" / memória cresce | `frontend-performance-audit`   |

## Verificação pré-merge

Confirme cada item do Modo 1 satisfeito + `tsgo --noEmit` e build do projeto verdes.

---

## References

- `references/layouts.tsx` — `SidebarShell` (flag `fullBleed`) + `SidebarLayout` (1440) + `SidebarChatLayout` (full-bleed).
- `references/grid-vs-stack.md` — heurística peers→grid / sequencial→stack, com exemplos.
- `references/overlays.md` — Dialog vs Sheet vs Drawer, tamanhos, geometria à prova de viewport na
  base do `DialogContent` (por que `max-h` + um único `overflow-y-auto` contêm os dois eixos),
  deep-link via search param, anti-padrões.
- `references/responsive-tabs.md` + `references/tabs.tsx` — abas responsivas (3+ triggers viram
  `Select` abaixo de 768px, automático e por CSS; context de valor espelhado do Radix; coleta de
  triggers na árvore; escapes `mobile="strip"`/`selectClassName`; mata o `isMobile ? Select : TabsList`
  no call site).
- `references/mobile-keyboard.md` + `references/form-dialog.tsx` — FormDialog (3 faixas ancoradas na
  visual viewport; por que `dvh` não resolve o teclado no iOS; meta viewport + safe-area; tabela de
  `size`; supressão dupla de autofocus; o que dá pra testar em jsdom/Playwright e o que exige device).
- `references/list-screen.md` + `references/data-list.tsx` + `references/list-toolbar.tsx` +
  `references/use-infinite-list.ts` — tela de lista (tabela↔card por role de coluna, scroll infinito
  de 10 em 10, busca/filtro/ordenação na URL, prefixo de query key que mantém a invalidação, sentinela
  sem double-fire; mata paginação por número de página e `<Table>` sem card no mobile).
- `references/pwa-mobile.md` — PWA instalado no celular (`minimal-ui` vs standalone e por que o iOS
  ignora; afordância de recarga obrigatória via `invalidateQueries`; `useIsStandalone`/pull-to-refresh
  com as constantes reais; safe-area + `viewport-fit=cover`; metas apple-\*; checklist de manifest).
- `references/settings-dialog.md` — hub de Settings deep-linkado (anatomia `h-[85vh] lg:max-w-6xl`,
  nav com grupos+busca, mobile lista→detalhe, permission gating, variante org-scoped).
- `references/toggle-card.md` + `references/toggle-card.tsx` — ToggleCard (toggle boolean como card
  clicável; chip + liquid wash + beam sincronizado; tabela de decisão vs CardCheckbox/Switch residual; keyframes).
- `references/confirm-dialog.tsx` — ConfirmDialog (padrão ÚNICO de confirmação destrutiva: AlertDialog
  central, `busy` async; mata tira inline/accordion/button-swap/`window.confirm`). Doc na seção confirm de `overlays.md`.
- `references/file-upload.md` — padrão de UI de upload (dropzone, 2 fluxos de título, menu de ações,
  preview PDF/Office/imagem, `useFileUpload`/`upload-error`/`file-types` canônicos). Espelha backend `uploads-storage`.
- `references/entity-picker.md` + `references/entity-picker.tsx` — EntityPicker (FK em form como
  combobox pesquisável no servidor + quick-create "Novo…" que auto-seleciona; tabela de decisão vs
  Select/DropdownMenu; contrato `useList`/`PagedResponse`+`search`; receitas de adaptação; mata
  Select estático e Input de ID cru).
- `references/permissions-display.md` — display de permissões agrupado por domínio + tabela canônica
  de verbos (ordem/cor/ícone); metadata no catálogo Pydantic; `PermissionGroupList`.
- `references/state-management.md` — os 5 níveis de state + anti-padrões.
- `references/performance-preventivo.md` — checklist preventivo de re-render/leak.
- `references/design-bar.md` — piso de qualidade estética (sem cara genérica de IA).
- `references/audit-checklist.md` — o punch-list do Modo 2, pronto pra copiar.
