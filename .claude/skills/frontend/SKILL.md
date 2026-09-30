---
name: frontend
description: PORTÃO obrigatório antes de QUALQUER construção/edição de UI (React 19 + TanStack + Tailwind 4 + shadcn) — layout, página, componente, overlay/dialog, form, tabela/lista/CRUD, abas, barra de filtros, upload de mídia, casca de app, PWA. Checklist ordenado de invariantes — layout dita a largura (1440 centrado, página sem max-w), Dialog-first sem Sheet lateral, grid p/ peers e 1 coluna p/ sequencial, onde mora o state, React 19, performance, Tailwind/shadcn semânticos, EntityPicker p/ FK, FormDialog (teclado do celular cobrindo campo ou botão salvar, dialog que sai da tela no mobile), ListToolbar+DataList (tabela vira card, scroll infinito, busca/filtros/ordenação na URL em UMA linha), 3+ abas viram Select no celular, responsivo por CSS (nunca useIsMobile), mobile-first bloqueante — e roteia pros skills profundos. MODO AUDITORIA: varrer/consertar a consistência de UI de um projeto (larguras divergentes, chat bugado, Sheet lateral, logo gigante, quebra no mobile, filtro torto ou em 2ª linha, tabela ilegível no celular, lista sem filtro/ordenação).
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
  **`max-w-[1440px]` centrado** + gutter fluido `px-[clamp(1rem,2vw,2rem)] py-4 md:py-6`, o MESMO
  gutter no header) · `SidebarChatLayout`
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
  correta (forms, inputs, variants). `Card` v4 sem padding vertical nos slots; `<Label>` sem
  `select-none`. Host externo novo → CSP no mesmo commit; falha de rede com mensagem única pt-BR.
  *deep: skill `shadcn` + `references/shadcn-v4-primitives.md` + `references/api-and-csp.md`.*
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
  por projeto. **Anexar pelo menu:** item que abre o file picker **NUNCA** chama
  `event.preventDefault()` no `onSelect` — o Radix mantém o menu aberto e modal (`pointer-events:
  none` na página + foco preso), e o sintoma sai como "não envia só com anexo"/"preciso clicar pra
  digitar". Depois que o anexo entra, o caret volta pro campo (crescimento da lista, em `rAF`), e
  **anexo sem texto é mensagem válida** (`hasText || hasAttachments`).
  Backend → gate `uploads-storage`. *deep: `references/file-upload.md`.*
- [ ] **8d. FK / seleção de entidade relacionada.** Campo de FK em form → **`EntityPicker`**
  (`ui/entity-picker.tsx`: Popover+Command `shouldFilter={false}`, busca **server-side** `?search=`
  com `limit` começando em 10 e crescendo de 10 em 10 ao rolar, `enabled` só com popover aberto, CTA "Novo…" que abre o `*FormDialog` da
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
  Nada abaixo da lista (o fim da página nunca chega). **Toolbar = UMA linha: busca/filtros/ordenação
  no canto superior ESQUERDO, ações à direita** — nunca ordenação numa 2ª linha embaixo dos botões;
  filtro é controle de UMA altura (rótulo dentro via `InputGroupAddon`, nunca `<Label>` empilhado);
  barra de filtros de dashboard segue o mesmo desenho (topo à esquerda, acima das abas). Backend: gate `database`
  (→ `list-pagination.md`). *deep: `references/list-screen.md` + `references/data-list.tsx` +
  `references/list-toolbar.tsx` + `references/use-infinite-list.ts` (canônicos).*
- [ ] **8g. Abas no mobile — 3+ abas viram `Select`.** `TabsList` com 3+ triggers renderiza um
  `Select` abaixo de 768px, **automaticamente** (o componente conta os filhos; call site escreve
  `<TabsList>` puro). A troca é CSS (`md:hidden` / `max-md:hidden`) com as duas formas montadas —
  **NUNCA `useIsMobile()`**, que resolve em `useEffect` e pisca + remonta o painel ativo. Escapes:
  `mobile="strip"` (aba ícone-only / rótulo de 1 palavra) e `selectClassName` (quando a lista divide
  linha flex com um vizinho). **PROIBIDO** `isMobile ? <Select…> : <TabsList…>` no call site — é
  exatamente o que o componente substitui. **Seções por rota** (tira de `<Button asChild><Link>`)
  com 3+ itens seguem a mesma regra: `Select` que navega abaixo de 768px + tira de `<Link>` acima,
  um array só. *deep: `references/responsive-tabs.md` +
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
larguras diferentes", "o chat buga", "o logo tá gigante"). Roda inline (single-agent). O runbook
inteiro — inventário por `rg`, punch-list, receitas de fix, ordem e verificação — está em
**`references/audit-checklist.md`**: abra, copie e marque.

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
  sem double-fire; mata paginação por número de página e `<Table>` sem card no mobile). Filtro de
  status com contagem por opção (`…/status-counts`) e ações em lote no menu `Ações` do toolbar
  (`references/bulk-actions-menu.tsx` + `references/use-list-selection.ts`).
- `references/agent-instructions.md` — tela de instruções de agente de IA do tenant (Markdown único
  montado no ChatGPT por botão com prompt do projeto, colado e mostrado renderizado; sem modos, sem
  preview lateral; o que a plataforma injeta em runtime fica FORA do texto; versões com restaurar).
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
- `references/shadcn-v4-primitives.md` — `Card` v4 (raiz manda no ritmo vertical), `<Label>` selecionável,
  campo nativo ≥16px.
- `references/api-and-csp.md` — CSP por diretiva (host externo novo no mesmo commit), `fetch` cru só p/
  API externa, mensagem única de falha de rede (`instanceof TypeError`).
- `references/audit-checklist.md` — o Modo 2 inteiro: inventário `rg`, punch-list, receitas, ordem e
  verificação.
