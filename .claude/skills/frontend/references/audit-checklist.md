# Audit Checklist — sweep de consistência (Modo 2)

Roda inline (single-agent), por projeto. Copie e marque.

## 1. Inventário (grep)

```bash
# páginas que setam largura própria (devem deixar a largura pro layout)
rg -n "mx-auto.*max-w-(2xl|3xl|4xl|5xl|6xl|7xl|\[)" frontend/src/routes frontend/src/components --glob '!**/ui/**'
# Sheet lateral fora do primitivo sidebar
rg -n "Sheet(Content|Trigger)?" frontend/src --glob '!**/ui/sidebar.tsx'
# altura mágica de viewport (quebra o chat)
rg -n "h-\[calc\(100dvh" frontend/src
# auto-colapso de sidebar / full-bleed atual
rg -n "useSidebarAutoCollapse|FULL_BLEED|isFullBleed|isCompact|variant=\"full\"" frontend/src
# candidatos a logo+banner / datas em grid
rg -n "grid-cols-2|aspect-video" frontend/src/components
# font-size base
rg -n "font-size|html\s*\{" frontend/src/index.css
# shell width atual
rg -n "max-w-\[1500px\]|max-w-\[1440px\]" frontend/src/components/layouts
# form dialog cru + altura estática (não sobrevive ao teclado do celular)
rg -ln "DialogContent" frontend/src/components --glob '!**/ui/**'
rg -n "max-h-\[8[05]vh\]|h-\[9[02]vh\]" frontend/src
# 2ª fonte de foco: o React chama .focus() independente do Radix
rg -n "autoFocus" frontend/src/components
# base do DialogContent contém os 2 eixos? (sem isso o dialog alto sai pela borda de cima)
rg -n "max-h-|overflow-y" frontend/src/components/ui/dialog.tsx
# responsivo resolvido em JS (pisca + remonta) em vez de CSS
rg -n "isMobile \?" frontend/src --glob '!**/ui/sidebar.tsx'
rg -n "<TabsList" frontend/src --glob '!**/ui/**'
# tabela sem card no mobile + column-collapse
rg -n "<Table" frontend/src/routes frontend/src/components
rg -n "hidden (sm|md|lg):table-cell" frontend/src
# paginação por número de página e fetch-all disfarçado
rg -n "page: *number|lastPage|Anterior|Próxima" frontend/src/routes
rg -n "limit: *[1-9]\d{2,}" frontend/src
# meta viewport (safe-area + teclado no Android)
rg -n "viewport" frontend/index.html
```

## 2. Punch-list (marcar por achado)

- [ ] **Página seta `max-w` próprio** → remover; largura é do layout.
- [ ] **Shell ≠ `max-w-[1440px]`** (ex.: 1500) → padronizar largura + padding `px-4 py-4 md:px-6 md:py-6`.
- [ ] **Chat com `h-[calc(100dvh-...)]`** → `flex min-h-0 w-full flex-1 flex-col overflow-hidden`.
- [ ] **`useSidebarAutoCollapse` no chat** → remover; sidebar fica normal como qualquer página.
- [ ] **Chat não usa `SidebarChatLayout`** → mover pra ele; criar o layout se não existir.
- [ ] **Sheet lateral** (detalhe/confirm/form) → Dialog (`sm:max-w-lg max-h-[85vh] overflow-y-auto`).
- [ ] **Sheet de filtro/nav mobile** → Drawer (vaul) ou Dialog.
- [ ] **Logo+Banner em `sm:grid-cols-2`** → empilhar full-width (`flex max-w-2xl flex-col gap-6`).
- [ ] **Conteúdo sequencial em grid** (datas dependentes lado a lado) → 1 coluna contida.
- [ ] **`font-size` base ausente/divergente** → `html { font-size: 17px }`.
- [ ] **Dialog com input em `DialogContent` cru / `max-h-[85vh]` / `h-[90vh]`** → `FormDialog`
      (`mobile-keyboard.md`). Tirar `autoFocus` do primeiro input e `overflow-y-auto` do `className`.
- [ ] **Base do `DialogContent` sem `max-h`/`overflow-y`** → `max-h-[calc(100dvh-2rem)]
      w-[calc(100%-2rem)] overflow-y-auto overscroll-contain` (e o `w-full` da base vira `w-[...]`).
      Sintoma: dialog sai pra cima/esquerda no celular (`overlays.md`).
- [ ] **`compactStyle` do `FormDialog` com `transform: "none"` mas sem `translate: "none"`** →
      adicionar. No Tailwind 4 o `-translate-x-1/2` sai pela propriedade autônoma `translate`, que
      `transform: none` não cancela: no celular o dialog anda meia largura pra esquerda e meia altura
      pra cima. Assinatura: borda direita em ~50% da largura do aparelho (`mobile-keyboard.md`).
- [ ] **Base do `DialogContent` sem a trava `max-md:`** → `max-md:max-h-[calc(100svh-3rem)]
      max-md:max-w-[calc(100%-2rem)]`. Sem ela `max-h-[85vh]`/`max-w-4xl` de call site vaza pro
      celular; no iOS `vh` é a viewport GRANDE, então 85vh ≈ tela inteira (`overlays.md`).
- [ ] **Campo nativo com fonte < 16px no celular** (`text-sm`/`text-xs` em `input.tsx`,
      `textarea.tsx`, `CommandInput`, `*ChipsInput`) → `text-base … md:text-sm`. Root de 17px faz
      `text-sm` = 14.875px: o iOS dá auto-zoom ao focar, pana a visual viewport e o dialog
      `position: fixed` some pra cima/pra esquerda (`mobile-keyboard.md`).
- [ ] **`isMobile ? <Select…> : <TabsList…>` no call site** → apagar o ramo, deixar `<TabsList>` puro
      (`responsive-tabs.md`); remover `useIsMobile` + imports `Select*` órfãos.
- [ ] **Meta viewport sem `viewport-fit=cover` + `interactive-widget=resizes-content`** → padronizar
      **junto** com safe-area (padding no shell, offset do Toaster, todo `fixed inset-0`).
- [ ] **`<Table>` sem card abaixo de 768px** → `DataList` (`list-screen.md`).
- [ ] **Paginação por número de página / `limit: 100..500`** → `useInfiniteList` 10 em 10.
- [ ] **Lista sem busca, sem filtro de status ou sem ordenação** → `ListToolbar` + `makeSortOptions`.
- [ ] **Filtro/busca/sort em `useState`** → URL (`validateSearch`); só o draft do input é local.
- [ ] **Ação (criar, totalizador) ABAIXO da lista** → subir pro `ListToolbar`.
- [ ] **Mobile 375px**: scroll horizontal, largura fixa em px sem fallback `w-full sm:w-[...]` → corrigir.

## 3. Ordem de execução

1. Layouts primeiro (`references/layouts.tsx`): `SidebarLayout` 1440 + `SidebarChatLayout` full-bleed;
   constante de roteamento no `_authenticated.tsx`.
2. Chat: remover altura mágica + auto-colapso; apontar pro `SidebarChatLayout`.
3. Remover `max-w` das páginas.
4. Overlays: Sheet → Dialog/Drawer.
5. Logo+Banner empilhado; datas em 1 coluna.
6. `font-size: 17px`.
7. `FormDialog` + meta viewport + compensações de safe-area (é o passo app-wide — commit próprio,
   revert cirúrgico).
8. `ListToolbar` + `DataList` nas telas de lista (depende do backend já devolver `has_more`/`sort`).

## 4. Verificação

`bun dev` (ou build). Confirme:

- páginas do mesmo layout com **largura idêntica** (1440 centrado);
- chat **preenche a área sem bug**, **sidebar intacta** (sem fechar/fullscreen);
- logo+banner **empilhados**, preview do banner grande;
- **nenhum Sheet lateral** no app;
- **mobile 375px**: 1 coluna, sem scroll horizontal, chat full-height, **toda tabela virou card**;
- com o **teclado aberto** num form dialog: footer visível, campo focado acima do teclado, dialog não
  sai pela borda de cima (Simulador iOS + Web Inspector; `mobile-keyboard.md` tem o checklist de 7).

> NÃO rodar o `check.sh` da raiz se houver workflow ativo (derruba test DB + build). Aqui é inline.
