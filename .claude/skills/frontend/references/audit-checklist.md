# Audit Checklist — sweep de consistência (Modo 2)

Roda inline (single-agent), por projeto. Copie e marque. Fonte única do Modo 2 — o `SKILL.md` só aponta
pra cá.

## 1. Inventário (grep)

```bash
# largura própria na página (a largura é do layout)
rg -n "max-w-\[?\d|max-w-(2xl|3xl|4xl|5xl|6xl|7xl)" frontend/src/routes frontend/src/components --glob '!**/ui/**'
# shell width atual + font-size base
rg -n "max-w-\[1500px\]|max-w-\[1440px\]" frontend/src/components/layouts
rg -n "font-size|html\s*\{" frontend/src/index.css
# Sheet lateral fora do primitivo sidebar
rg -n "Sheet(Content|Trigger)?\b" frontend/src --glob '!**/ui/sidebar.tsx'
# altura mágica de viewport (quebra o chat) + auto-colapso / full-bleed
rg -n "h-\[calc\(100dvh" frontend/src
rg -n "useSidebarAutoCollapse|FULL_BLEED|isFullBleed|isCompact|variant=\"full\"" frontend/src
# candidatos a logo+banner / datas em grid
rg -n "grid-cols-2|aspect-video" frontend/src/components
# Switch-in-card → ToggleCard · nuvem de badges → PermissionGroupList
rg -n "<Switch" frontend/src --glob '!**/ui/**'
rg -n "permissions.map|permission.*Badge" frontend/src/components
# Select de FK que cresce / Input de ID cru → EntityPicker
rg -n "SelectTrigger" frontend/src/components frontend/src/routes --glob '!**/ui/**'
rg -n 'placeholder=".*(ID|UUID|[Ii]dentificador)' frontend/src
# feedback / casca: AlertDialog cru, confirm nativo, "Nenhum…" solto, resíduo morto
rg -n "AlertDialog" frontend/src --glob '!**/ui/**'
rg -n "window\.confirm|[^.]alert\(" frontend/src
rg -n ">Nenhum" frontend/src --glob '!**/ui/**'
fd -t f 'breadcrumb.tsx|Can.tsx|bulk-action-bar.tsx' frontend/src
# form dialog cru + altura estática + 2ª fonte de foco (o React chama .focus() independente do Radix)
rg -ln "DialogContent" frontend/src/components --glob '!**/ui/**'
rg -n "max-h-\[8[05]vh\]|h-\[9[02]vh\]" frontend/src
rg -n "autoFocus" frontend/src/components
# base do DialogContent (2 eixos + trava max-md:) · compactStyle zera transform E translate?
rg -n "max-h-|overflow-y|max-md:" frontend/src/components/ui/dialog.tsx
rg -n "transform|translate" frontend/src/components/ui/form-dialog.tsx
# largura útil: grid/flex de página em viewport (deveria ser @…/main:), dialog com vh/vw, abas com h-auto, subtítulo sem truncate
rg -n "\b(sm|md|lg|xl):(grid-cols|flex-row)" frontend/src/routes frontend/src/components --glob '!**/ui/**'
rg -n "h-\[\d+vh\]|max-h-\[\d+vh\]|w-\[\d+vw\]" frontend/src --glob '!**/ui/**'
rg -n "<TabsList[^>]*(h-auto|flex-wrap)" frontend/src
rg -n "subtitle" frontend/src/components/layouts | rg -v "truncate"
# campo nativo < 16px → auto-zoom do iOS
rg -n "text-(xs|sm)" frontend/src/components/ui/{input,textarea,command,input-group,combobox}.tsx
# responsivo resolvido em JS (pisca + remonta) em vez de CSS
rg -n "isMobile \?|useIsMobile\(" frontend/src --glob '!**/ui/sidebar.tsx'
rg -n "<TabsList" frontend/src --glob '!**/ui/**'
rg -n '\? "default" : "outline"' frontend/src --glob '!**/ui/**'   # tira de seções por rota
# listas: tabela sem card, column-collapse, paginação por página, fetch-all, label empilhado no toolbar
rg -n "<Table" frontend/src/routes frontend/src/components
rg -n "hidden (sm|md|lg):table-cell" frontend/src
rg -n "page: *number|lastPage|Anterior|Próxima" frontend/src/routes   # paginação feita à mão (usar usePagedList/ListPagination)
# lista no padrão 2026-10-09: ⋮ na toolbar, sem IntersectionObserver, picker sem limit crescente, CTA fora do CommandList
rg -L "ListOptionsMenu" $(rg -l "<ListToolbar" frontend/src/routes frontend/src/components)   # tela de lista sem o ⋮ (sub-lista em aba é exceção)
rg -n "IntersectionObserver" frontend/src/hooks frontend/src/components/ui   # sentinela de lista/picker tem que ser scroll listener
rg -n "params\.limit|limit: *\w+\.limit" frontend/src/hooks frontend/src/components --glob '*[Pp]icker*' --glob '*use[A-Z]*'   # limit na key de adapter de picker
rg -n "CommandList" -A30 frontend/src/components/ui/entity-picker.tsx | rg "onCreateNew|createLabel"   # CTA "Novo" dentro do CommandList
rg -n "<DataList" -A12 frontend/src/routes | rg -v "countLabel" | rg "total="   # total só no rodapé: contagem vem do ListSummary no topo
rg -n "limit: *[1-9]\d{2,}" frontend/src
rg -n "filters=\{" -A12 frontend/src --glob '!**/ui/**' | rg "<Label"
# meta viewport (safe-area + teclado) · manifest · reload que descarta bundle + access
rg -n "viewport" frontend/index.html
rg -n '"display"|"short_name"|TanStack App' frontend/public/manifest.json
rg -n "location.reload\(\)" frontend/src
# anexo: item de menu que prende o menu modal · foco depois de anexar · envio exigindo texto
rg -n -B2 "openFileDialog\(\)" frontend/src --glob '!**/ai-elements/**' | rg "preventDefault"
rg -n "preventDefault" frontend/src/components/ai-elements/prompt-input.tsx
rg -n "hasAttachments|disabled=\{!.*(input|text)" frontend/src/components/chat
# hosts externos × CSP
rg -no 'fetch\("https://[a-z0-9.-]+' frontend/src
rg -n '<script|<iframe|<audio|<video' frontend/src --glob '!**/*.test.*'
rg -o 'Content-Security-Policy "[^"]*"' config/nginx/snippets/security-headers-base.conf
```

## 2. Punch-list (marcar por achado)

### Layout & casca

- [ ] **Página seta `max-w` próprio** → remover; largura é do layout.
- [ ] **Shell ≠ `max-w-[1440px]`** (ex.: 1500) → padronizar largura + gutter fluido
      `px-[clamp(1rem,2vw,2rem)] py-4 md:py-6`, o MESMO gutter no header (senão título e conteúdo
      caem em bordas esquerdas diferentes). O teto é freio de 2K/4K; em 1920@125% o viewport é 1536 e
      quem o usuário sente é o gutter, não o cap.
- [ ] **Chat com `h-[calc(100dvh-...)]`** → `flex min-h-0 w-full flex-1 flex-col overflow-hidden`.
- [ ] **`useSidebarAutoCollapse` no chat** → remover; sidebar fica normal como qualquer página.
- [ ] **Chat não usa `SidebarChatLayout`** → mover pra ele; criar o layout se não existir.
- [ ] **Header do chat capado em 1440** enquanto o conteúdo é full-bleed → header full-bleed também.
- [ ] **Logo+Banner em `sm:grid-cols-2`** → empilhar full-width (`flex max-w-2xl flex-col gap-6`).
- [ ] **Conteúdo sequencial em grid** (datas dependentes lado a lado) → 1 coluna contida.
- [ ] **`font-size` base ausente/divergente** → `html { font-size: 17px }` (salvo exceção registrada
      do projeto).

### Largura útil (2026-10-09)

- [ ] **`(sm|md|lg|xl):grid-cols-*`/`flex-row` de layout em `routes/` ou componente de domínio** →
      `@xl/main:`/`@2xl/main:`/`@4xl/main:`/`@6xl/main:` (ou `@container` próprio no componente reusável).
- [ ] **Card que é célula de grid de várias colunas medindo `/main`** → `@container` no próprio card +
      `@sm:`/`@lg:` (a página é larga, o card não — ex.: card de listagem de veículo, 2026-10-09).
- [ ] **`/main` dentro de Dialog/Popover/Drawer** → nunca casa (o conteúdo é portaled para fora do
      `@container/main`; fica preso no layout de 1 coluna). Dentro de overlay: viewport `md:/lg:`
      (overlay é `fixed` na viewport) ou `@container` no corpo do dialog. Vale para o hub de Settings.
- [ ] **`\@` literal em className** (`rg -n '\\@' src`) → classe não compila e o layout quebra calado;
      vem de escape de shell em edição em massa (`sd`/`sed`). Edite com Edit/script Python.
- [ ] **Wrapper de conteúdo do shell sem `@container/main`** → adicionar (e no `<main>` do full-bleed).
- [ ] **`TabsList` com `h-auto`/`flex-wrap`** → remover; o componente compacta e vira `Select`.
- [ ] **Subtítulo do header sem `truncate max-sm:hidden`** / bloco do título sem `min-w-0`.
- [ ] **Texto secundário largo virando altura no celular** → `max-sm:hidden` ou `truncate`/`line-clamp-1`.
- [ ] **Valor monetário/KPI cortado** → `tabular-nums whitespace-nowrap` + tamanho por container.
- [ ] **Conferência visual** em 1024 / 1280 / 1366 com a sidebar ABERTA e em 390: sem 2ª linha de
      abas, sem scroll horizontal, sem valor cortado.

### Overlays & forms

- [ ] **Sheet lateral** (detalhe/confirm/form) → Dialog (a geometria vem da base do `DialogContent`;
      com campo → `FormDialog`). **Sheet de filtro/nav mobile** → Drawer (vaul) ou Dialog.
- [ ] **`vh`/`vw` em `DialogContent` (`h-[85vh]`, `max-h-[92vh]`, `w-[95vw]`) / dialog com input em `DialogContent` cru** → `FormDialog`
      (`mobile-keyboard.md`). Tirar `autoFocus` do primeiro input e `overflow-y-auto` do `className`.
- [ ] **Base do `DialogContent` sem `max-h`/`overflow-y`** → `max-h-[calc(100dvh-2rem)]
      w-[calc(100%-2rem)] overflow-y-auto overscroll-contain` (e o `w-full` da base vira `w-[...]`).
      Sintoma: dialog alto sai pela borda de cima e o conteúdo fica inalcançável (`overlays.md`).
- [ ] **Base do `DialogContent` sem a trava `max-md:`** → `max-md:max-h-[calc(100svh-3rem)]
      max-md:max-w-[calc(100%-2rem)]`. Sem ela `max-h-[85vh]`/`max-w-4xl` de call site vaza pro
      celular; no iOS `vh` é a viewport GRANDE, então 85vh ≈ tela inteira (`overlays.md`).
- [ ] **`compactStyle` do `FormDialog` com `transform: "none"` mas sem `translate: "none"`** →
      adicionar. No Tailwind 4 o `-translate-x-1/2` sai pela propriedade autônoma `translate`, que
      `transform: none` não cancela: no celular o dialog anda meia largura pra esquerda e meia altura
      pra cima. Assinatura: borda direita em ~50% da largura do aparelho (`mobile-keyboard.md`).
- [ ] **Campo nativo com fonte < 16px no celular** (`text-sm`/`text-xs` em `input.tsx`,
      `textarea.tsx`, `CommandInput`, `*ChipsInput`) → `text-base … md:text-sm`. Root de 17px faz
      `text-sm` = 14.875px: o iOS dá auto-zoom ao focar e o dialog `position: fixed` some pra cima/pra
      esquerda (`mobile-keyboard.md`).
- [ ] **Meta viewport sem `viewport-fit=cover` + `interactive-widget=resizes-content`** → padronizar
      **junto** com safe-area (padding no shell, offset do Toaster, todo `fixed inset-0`).

### Componentes

- [ ] **Padding v3 empilhado sobre `Card` v4** (`CardContent` com `pt-6`/`py-10`/`p-4`, `CardHeader`
      com `pb-2`/`space-y-*`, `CardFooter` com `border-t py-6`) → remover o vertical do slot; card
      compacto vira `<Card className="gap-4 py-4">` + slots `px-4` (`shadcn-v4-primitives.md`).
- [ ] **Switch dentro de card/row com rótulo** (fora de célula de tabela densa) → `ToggleCard`
      (`toggle-card.md`).
- [ ] **Nuvem plana de badges de permissões** (Dialog info, Efetivas) → `PermissionGroupList`
      agrupado por domínio (`permissions-display.md`).
- [ ] **Select estático ou Input de ID/UUID cru para QUALQUER FK de entidade do tenant** (cliente,
      veículo, fornecedor, membro…) → wrapper `XPicker` (`EntityPicker` + `usePickerLabel` + "Novo…",
      `entity-picker.md`). Select só sobra para enum fechado/catálogo de sistema que **não** é FK —
      "a lista é pequena" não é justificativa (ela cresce).
- [ ] **`<AlertDialog*>` cru fora de `components/ui/`, `window.confirm`/`alert`** → `ConfirmDialog`
      (`feedback-states.md`).
- [ ] **"Nenhum X" em `<p>` solto, `EmptyState` privado dentro de componente, lista que mostra vazio
      quando a query falhou** → `ui/empty-state.tsx` + `ErrorState` (`feedback-states.md`).
- [ ] **App sem `NetworkStatusBanner` no shell** (ou deslogando/redirecionando por evento `offline`)
      → faixa única, só leitura de `navigator.onLine` (`feedback-states.md`).
- [ ] **Campo pt-BR (telefone/CPF/CNPJ/CEP/data/placa) com `onChange` + regex ad-hoc** →
      `MaskedInput` + `lib/utils/masks.ts` (item 8h do `SKILL.md`).
- [ ] **Impressão por `body * { visibility: hidden }`, `<iframe>`/`window.open` com HTML manual ou
      lib de PDF no cliente** → `PrintSheet` + `Doc*` (`printing.md`).
- [ ] **Resíduo morto da casca**: `ui/breadcrumb.tsx`, `auth/Can.tsx`, `ui/bulk-action-bar.tsx`,
      `documents/DocumentPreviewDialog.tsx` do nexarena sem import → apagar (e imports órfãos);
      login em `/login` → `/auth/login` (skill `app-scaffold`).
- [ ] **`event.preventDefault()` no `onSelect` do item que abre o file picker** → tirar; o menu tem
      que fechar. Radix mantém o menu ABERTO e modal (`pointer-events: none` na página + foco preso),
      então o clique/tecla seguinte só fecha o menu — reportado como "não envia só com anexo" e
      "preciso clicar pra digitar" (`file-upload.md`).
- [ ] **Anexo entra e o foco fica fora do campo de texto** → focar no crescimento da lista, em `rAF`
      (o `FocusScope` do Radix devolve o foco ao trigger num `setTimeout(0)`) — `file-upload.md`.
- [ ] **Envio de chat exigindo texto** (`disabled={!input}` no submit, gate só de texto no handler) →
      `hasText || hasAttachments`; anexo sozinho é mensagem válida (`file-upload.md`).

### Listas, abas & filtros

- [ ] **`<Table>` sem card abaixo de 768px** → `DataList` (`list-screen.md`). Column-collapse
      (`hidden lg:table-cell`) fica, mas só pra densidade acima de 768px.
- [ ] **`limit: 100..500` (fetch-all)** → `useCollectionList` (rolagem contínua default, páginas no ⋮;
      `list-screen.md`). Modo fixo no código sem o usuário poder trocar também é achado.
- [ ] **Tela de lista sem `menu={<ListOptionsMenu …/>}` na `ListToolbar`** (exceto sub-lista em
      aba/painel: movimentações, notificações, timeline) → adicionar o ⋮ + `useListPreferences`.
- [ ] **Contagem só no rodapé / pílula sticky / "Carregar mais" sem total** → `ListSummary` no TOPO
      (o `data-list.tsx` canônico já faz; re-vendorar).
- [ ] **`IntersectionObserver`/`rootMargin` no sentinel de lista ou picker** → `useInfiniteScrollSentinel`
      (scroll listener) + botão "Carregar mais"; o observer encadeia páginas sem o usuário rolar.
- [ ] **Adapter de `EntityPicker` com `limit` crescente na query key** (`params.limit`, "10 em 10") →
      `useInfiniteList`/`useInfinitePages` (páginas anexadas; `entity-picker.md`). CTA "Novo…" dentro
      do `CommandList` → rodapé fixo fora do scroll. Item sem wrapper `flex-1 min-w-0` → 2ª coluna torta.
- [ ] **`useCrud.useList` sem `keepPreviousData`** (tabela pisca ao trocar página/filtro) → restaurar
      `placeholderData: keepPreviousData` (`list-screen.md`).
- [ ] **Lista sem busca, sem filtro de status ou sem ordenação** → `ListToolbar` + `makeSortOptions`.
- [ ] **Filtro/busca/sort em `useState`** → URL (`validateSearch`); só o draft do input é local.
- [ ] **Ação (criar, totalizador) ABAIXO da lista** → subir pro `ListToolbar`/topo.
- [ ] **Filtro/ordenação numa 2ª linha à direita, embaixo das ações** → re-vendorar `list-toolbar.tsx`;
      barra ad-hoc → controles no topo à esquerda, ações à direita (`list-screen.md` → Geometria).
- [ ] **`<Label>` empilhado sobre filtro do toolbar** (data "De/Até" desce meia linha) → rótulo dentro
      do controle via `InputGroupAddon` + `aria-label`, sem `id`/`htmlFor`.
- [ ] **`isMobile ? <Select…> : <TabsList…>` / `useIsMobile()` trocando layout** → dual-render por CSS
      (`responsive-tabs.md`); remover `useIsMobile` + imports `Select*` órfãos. Barra de filtros com o
      mesmo vício → botão "Filtros" `md:hidden` + `FormDialog`, estado de popover por superfície.
- [ ] **Tira de 3+ seções por rota (`<Button asChild><Link>` + `flex-wrap`) sem forma mobile** →
      `Select` que navega `md:hidden` + `<nav>` `max-md:hidden` (`responsive-tabs.md`).

### Mobile, PWA & CSP

- [ ] **Mobile 375px**: scroll horizontal, largura fixa em px sem fallback `w-full sm:w-[...]` → corrigir.
- [ ] **Manifest com `display: standalone`, nome de scaffold, sem `scope`/maskable — ou app instalado
      sem botão de reload** → `pwa-mobile.md` (`minimal-ui` + afordância in-app; no iOS o usuário não
      tem como recarregar).
- [ ] **Host externo usado pelo front que não está no CSP** → liberar em
      `config/nginx/snippets/security-headers-base.conf`, na diretiva certa e no mesmo commit
      (`api-and-csp.md`). Sintoma: a tela não quebra, só o form não salva — erro só no console.

## 3. Receitas

**Layouts** → adotar `layouts.tsx`: `SidebarShell` interno (flag `fullBleed` p/ o header) +
`SidebarLayout` (1440) + `SidebarChatLayout` (full-bleed). Escolha por rota numa constante no
`_authenticated.tsx`.

**Chat height** (antes → depois):

```tsx
// ANTES (quebra quando header muda de altura / sidebar colapsa)
<div className="flex h-[calc(100dvh-2.5rem)] w-full flex-col overflow-hidden">
// DEPOIS (participa da cadeia flex do SidebarChatLayout)
<div className="flex min-h-0 w-full flex-1 flex-col overflow-hidden">
```

**Sheet → Dialog**: trocar `Sheet/SheetContent/SheetHeader/SheetTitle` por
`Dialog/DialogContent/DialogHeader/DialogTitle`, `side="..."` sai; largura por `sm:max-w-*` se precisar
— altura e scroll já vêm da base (`overlays.md`). Com campo editável, é `FormDialog`.

**Página com max-w próprio**: remover o `mx-auto max-w-*` do wrapper — o layout já centra/capa em 1440.

## 4. Ordem de execução

1. Layouts primeiro (`layouts.tsx`): `SidebarLayout` 1440 + `SidebarChatLayout` full-bleed;
   constante de roteamento no `_authenticated.tsx`.
2. Chat: remover altura mágica + auto-colapso; apontar pro `SidebarChatLayout`.
3. Remover `max-w` das páginas.
4. Overlays: Sheet → Dialog/Drawer.
5. Logo+Banner empilhado; datas em 1 coluna.
6. `font-size: 17px`.
7. `FormDialog` + meta viewport + compensações de safe-area (é o passo app-wide — commit próprio,
   revert cirúrgico).
8. `ListToolbar` + `DataList` nas telas de lista (depende do backend já devolver `has_more`/`sort`).

## 5. Verificação

`bun dev` (ou build) + `tsgo --noEmit`. Confirme:

- páginas do mesmo layout com **largura idêntica** (1440 centrado);
- chat **preenche a área sem bug**, **sidebar intacta** (sem fechar/fullscreen), header alinhado;
- logo+banner **empilhados**, preview do banner grande;
- **nenhum Sheet lateral** no app;
- **mobile 375px**: 1 coluna, sem scroll horizontal, chat full-height, **toda tabela virou card**,
  toolbar em `[busca]` + `[Filtros][ações]`;
- com o **teclado aberto** num form dialog: footer visível, campo focado acima do teclado, dialog não
  sai pela borda de cima (Simulador iOS + Web Inspector; `mobile-keyboard.md` tem o checklist de 7).

> NÃO rodar o `check.sh` da raiz se houver workflow ativo (derruba test DB + build). Aqui é inline.
