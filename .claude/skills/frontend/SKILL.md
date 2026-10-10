---
name: frontend
description: PORTÃO obrigatório antes de QUALQUER construção/edição de UI (React 19 + TanStack + Tailwind 4 + shadcn) — layout, página, componente, overlay/dialog, form, tabela/lista/CRUD, abas, barra de filtros, upload de mídia, impressão/PDF, estados vazio/erro/offline, máscaras, casca de app, PWA, telas canônicas (Equipes, inbox WhatsApp, config de agente de IA). Checklist ordenado de invariantes — layout dita a largura (1440 centrado, página sem max-w), Dialog-first sem Sheet lateral, grid p/ peers e 1 coluna p/ sequencial, onde mora o state, React 19, performance, Tailwind/shadcn semânticos, EntityPicker p/ FK, FormDialog (teclado do celular cobrindo campo ou botão salvar, dialog que sai da tela no mobile), ListToolbar+DataList (tabela vira card, modo por tela: rolagem contínua default + páginas numeradas no ⋮, totais no topo, busca/filtros/ordenação na URL em UMA linha), 3+ abas viram Select no celular, responsivo por CSS (nunca useIsMobile), mobile-first bloqueante — e roteia pros skills profundos. MODO AUDITORIA: varrer/consertar a consistência de UI de um projeto (larguras divergentes, chat bugado, Sheet lateral, logo gigante, quebra no mobile, filtro torto ou em 2ª linha, tabela ilegível no celular, lista sem filtro/ordenação).
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
  lugar (constante no `_authenticated.tsx`). **Largura útil, não viewport:** o wrapper de conteúdo do
  shell é `@container/main`; layout dentro da página responde a ele (`sm:`→`@xl/main:`, `md:`→
  `@2xl/main:`, `lg:`→`@4xl/main:`, `xl:`→`@6xl/main:`), porque com a sidebar aberta o notebook tem só
  ~700–1100px úteis. Viewport só p/ shell/overlays/trocas mobile canônicas. **Header:** título
  `min-w-0`, `h1 truncate`, subtítulo `truncate max-sm:hidden`. **Texto secundário** (descrição de
  card/seção, ajuda) nunca vira altura no celular: `max-sm:hidden` ou 1 linha `truncate`.
  *deep: `references/layouts.tsx`.*
- [ ] **2. Overlays.** Dialog-first para tudo (form, detalhe, confirm, picker). **ZERO Sheet lateral
  no app.** Mobile nav/filtro → Dialog ou Drawer (vaul). Tamanho por necessidade; a **geometria** é
  da base do `DialogContent` (`max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] overflow-y-auto` — capa
  a altura e contém os DOIS eixos; sem isso o dialog alto sai pela borda de cima, fora do alcance de
  qualquer scroll, e o conteúdo largo faz a página inteira panar) **+ a trava
  `max-md:max-h-[calc(100svh-3rem)] max-md:max-w-[calc(100%-2rem)]`**, que impede o call site de vazar
  medida de desktop (`max-w-4xl`) pro celular — no iOS `vh` é a viewport GRANDE. **PROIBIDO
  `vh`/`vw`/`h-[Nvh]`/`max-h-[Nvh]`/`w-[Nvw]` no call site** (altura grande = `h-[calc(100dvh-2rem)]`).
  Campo nativo dentro do overlay vai a **`text-base` no celular** (< 16px = auto-zoom do iOS, que pana
  a visual viewport e leva o dialog pra fora da tela). Overlay bookmarkável (hub de settings, inspector) →
  **deep-link via search param**; 2+ itens de config na sidebar → consolidar no hub (`?settings=<seção>`, padrão em todos os apps menos optimuslar). Confirmação
  destrutiva → **`ConfirmDialog`** central (NUNCA tira inline/accordion/button-swap/`window.confirm`).
  *deep: `references/overlays.md` + `references/settings-dialog.md` + `references/confirm-dialog.tsx`.*
- [ ] **3. Grid vs Stack.** Itens paralelos/peers → **grid** responsivo à largura útil
  (`grid-cols-1 @xl/main:grid-cols-2 @4xl/main:grid-cols-3`, ou `auto-fill minmax`; KPI/dinheiro
  `tabular-nums whitespace-nowrap`, nunca cortado). Conteúdo sequencial/dependente (datas início→fim, logo→banner, passos) → **1
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
  three-dots). Canônico = **promoservice** (`useFileUpload` + `ui/file-dropzone`/`image-dropzone`,
  `upload-error`, `file-types`) + **`DocumentSlot`** do balizap (slot predefinido com título fixo).
  **Progresso real de envio**: `ApiClient.upload(url, form, { onProgress })` (XHR) +
  `useUploadMutation({ mutationFn: (vars, onProgress) => … })` → `{ …mutation, progress: number|null }`
  alimenta `<UploadProgress value>` (100% = "Processando..."); `useFileUpload` segue sendo o
  **validador puro** (tipo/tamanho → `UploadError` pt-BR). Dois fluxos de título (slot predefinido vs
  captura inline). **Criar com arquivos pendentes** (entidade ainda sem id — variante do nexarena):
  arquivos ficam em state local no form de criação e sobem em sequência após o `create` devolver o id.
  Preview `DocumentPreviewDialog`; delete via `ConfirmDialog`. Componentes apresentacionais
  (callbacks); dados por projeto. **Anexar pelo menu:** item que abre o file picker **NUNCA** chama
  `event.preventDefault()` no `onSelect` — o Radix mantém o menu aberto e modal (`pointer-events:
  none` na página + foco preso), e o sintoma sai como "não envia só com anexo"/"preciso clicar pra
  digitar". Depois que o anexo entra, o caret volta pro campo (crescimento da lista, em `rAF`), e
  **anexo sem texto é mensagem válida** (`hasText || hasAttachments`).
  Backend → gate `uploads-storage`. *deep: `references/file-upload.md`.*
- [ ] **8d. FK / seleção de entidade relacionada — `EntityPicker` em TODA FK.** Campo de FK em form
  (cliente, veículo, fornecedor, produto, membro…) → **`EntityPicker`** (`ui/entity-picker.tsx`:
  Popover+Command `shouldFilter={false}`, busca **server-side** `?search=`, páginas de 10 **anexadas**
  (`useInfiniteList`/`useInfinitePages`, shape `EntityPickerSource`; nunca `limit` crescente na
  query key), `<Popover modal>`, `enabled` só com popover aberto, rodapé fixo fora do scroll com
  "+ Novo…" à esquerda (abre o `*FormDialog` e auto-seleciona no `onSaved`) e "X de Y" à direita). **Um wrapper por entidade**
  (`CustomerPicker`, `VehiclePicker`…) que fixa `useList`/rótulo/`FormDialog`, e o form usa o wrapper
  + **`usePickerLabel`** (guarda o rótulo da seleção para o campo não mostrar UUID/"…" enquanto a
  lista carrega ou na edição). **PROIBIDO**: `Select` estático p/ FK (mesmo "lista pequena" — ela
  cresce); `Input` de ID/UUID cru; FK digitada solta. `Select` só para **enum fechado/catálogo de
  sistema que não é FK** (status, tipo, role de sistema); seletor de contexto global (trocar org
  ativa) segue `DropdownMenu`. Backend: o MESMO list endpoint paginado (`PagedResponse` + `search`
  ILIKE), sem endpoint de autocomplete. **FK limpa**: ao auditar, nenhum `<Select>`/`Input` de id
  para FK sobrando (receita `rg` em `entity-picker.md`). *deep: `references/entity-picker.md` +
  `references/entity-picker.tsx` (canônico).*
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
  + `DataList`** (`ui/list-toolbar.tsx`, `ui/data-list.tsx`): UMA definição de coluna renderiza a
  tabela (≥768px) e a pilha de cards (<768px); busca com debounce + mínimo 3 chars; filtros e
  ordenação. **Modo POR TELA (decisão 2026-10-09): rolagem contínua é o DEFAULT, páginas numeradas é a
  opção 2**, escolhida no ⋮ no fim da toolbar (`ListOptionsMenu` no slot `menu`; preferência por
  tela em localStorage via `useListPreferences`). Tela = `useCollectionList(endpoint, params,
  {mode, page, pageSize})` espalhado em `<DataList {...list}>`. **Totais no topo** (`ListSummary`),
  embaixo só `ListPagination hideRange` ou o loader infinito; infinito carrega só ao rolar de verdade
  até o fim (listener de scroll, SEM `IntersectionObserver`) + botão "Carregar mais". Tela cujo
  clique principal abre o item ganha a tira **"Abertos recentemente"** (5 últimos, `useRecentlyOpened`).
  `q`/`status`/`sort`/`order` (e `page`, só no modo páginas) na URL (`validateSearch`) — nunca
  `useState`. **Toolbar = UMA linha: busca/filtros/ordenação no canto
  superior ESQUERDO, ações à direita** — nunca ordenação numa 2ª linha embaixo dos botões; filtro é
  controle de UMA altura (rótulo dentro via `InputGroupAddon`, nunca `<Label>` empilhado); barra de
  filtros de dashboard segue o mesmo desenho (topo à esquerda, acima das abas). Query que falhou ≠
  lista vazia (`ErrorState`, 8i). **Criar/editar = `FormDialog`** aberto da lista; **detalhe = página
  com abas**. Ação em lote só quando existir: `useListSelection` + `BulkActionsMenu` no toolbar
  (nunca barra solta). Backend: gate `database` (→ `list-pagination.md`). *deep:
  `references/list-screen.md` + `references/data-list.tsx` + `references/list-toolbar.tsx` +
  `references/list-options.tsx` + `references/list-pagination.tsx` +
  `references/use-collection-list.ts` + `references/use-infinite-list.ts` +
  `references/use-paged-list.ts` + `references/use-recently-opened.ts` + `references/list-page.ts` +
  `references/bulk-actions-menu.tsx` + `references/use-list-selection.ts` (canônicos).*
- [ ] **8g. Abas que não cabem — cheio → compacto → `Select`, nunca 2ª linha.** `Tabs` é
  `@container/tabs`; `TabsList` (`min-h-8`, `flex-nowrap`, triggers `flex-none`) com 3+ triggers
  escolhe a forma pela LARGURA da `Tabs` e pelo nº de abas (mapa estático por faixa): cheio →
  compacto (padding/gap menores, ícone FICA — usuário 2026-10-09) → `Select`, **automaticamente** (call site escreve
  `<TabsList>` puro; PROIBIDO `h-auto flex-wrap` — o `h-8` fixo antigo fazia a 2ª linha sobrepor o
  conteúdo; decisão 2026-10-09). A troca é CSS (container query) com as duas formas montadas —
  **NUNCA `useIsMobile()`**, que resolve em `useEffect` e pisca + remonta o painel ativo. Escapes:
  `mobile="strip"` (aba ícone-only / rótulo de 1 palavra) e `selectClassName` (quando a lista divide
  linha flex com um vizinho). **PROIBIDO** `isMobile ? <Select…> : <TabsList…>` no call site — é
  exatamente o que o componente substitui. **Seções por rota** (tira de `<Button asChild><Link>`)
  com 3+ itens seguem a mesma regra: `Select` que navega abaixo de 768px + tira de `<Link>` acima,
  um array só. *deep: `references/responsive-tabs.md` +
  `references/tabs.tsx` (canônico).*
- [ ] **8h. Máscaras de input — nunca `onChange` ad-hoc.** Campo pt-BR com formato (telefone, CPF,
  CNPJ, CEP, data, **placa**) → **`MaskedInput`** (`ui/masked-input.tsx`, `react-imask`) com
  `mask: "phone" | "cpf" | "cnpj" | "cep" | "date" | "plate"`. `value`/`onChange` trafegam o valor
  **cru** (dígitos; `plate` = A-Z/0-9, "ABC1D23"/"ABC1234") — `unmaskOnSubmit={false}` devolve o
  texto mascarado. Máscara nova = um caso em `getMaskOptions` + `unmaskValue` de
  `lib/utils/masks.ts` (+ `formatX`, `isValidCNPJ`, `isValidPlate`, `unmaskPlate`), nunca regex solta
  no call site. Canônico = kailos (`lib/utils/masks.ts` + `ui/masked-input.tsx`); os outros apps
  sincronizam com ele (placa entra em todos). Dinheiro **não** é máscara compartilhada (por projeto).
- [ ] **8i. Estados de feedback — um componente por situação.** Vazio → **`EmptyState`**
  (`ui/empty-state.tsx`; o mesmo do `DataList`; nunca "Nenhum…" em `<p>` solto); **query que falhou
  ≠ vazio** (`ErrorState` + "Tentar novamente"; `RouteErrorFallback` p/ rota); sem rede →
  `NetworkStatusBanner` (+ `useOnlineStatus`) montado UMA vez no shell — faixa, nunca toast, nunca
  desloga; confirmação destrutiva → **`ConfirmDialog` único** (`AlertDialog` cru PROIBIDO fora de
  `ui/`); resultado de ação → toast sonner; primeira carga → `Skeleton` com a forma do conteúdo.
  *deep: `references/feedback-states.md`.*
- [ ] **8j. Impressão / PDF — `PrintSheet` + `Doc*`.** Documento imprimível (OS, orçamento,
  contrato, termo, check-list, rota pública por token com "Imprimir") → **`window.print()` sobre uma
  folha HTML**: `PrintSheet` (portal no `body`, A4 14mm, thead repetido, CSS embutido, rodapé de uma
  linha, `DocSignatures` no `footer`) + primitivos `DocSection/DocItem/DocFacts/DocTable/DocFieldGrid/
  DocTotals/DocPhotoGrid` (dados por props tipadas; kit em `components/print/` de kailos/promoservice) + `PrintableDocumentDialog` (`components/print/`) (prévia + "Imprimir / salvar PDF"). Zero lib de PDF
  no cliente; **NUNCA** `body * { visibility: hidden }`, `<iframe>`/`window.open` com HTML à mão,
  fonte variável na folha. *deep: `references/printing.md`.*
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
  **"Instalar app" obrigatório em app real, SÓ no menu do usuário (rodapé da sidebar, área
  logada — nunca login/landing/header)**: `beforeinstallprompt` capturado no boot + dialog de
  passos no iOS/iPadOS, dialog irmão do `DropdownMenu`. `sw.js` push-only (sem `fetch`/cache)
  registrado no boot; cache offline só com pedido explícito. *deep: `references/pwa-mobile.md` §6
  + `references/install-prompt.ts`/`pwa-platform.ts`/`install-app-button.tsx` (canônicos).*
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
| Montar casca de app autenticada (sidebar/auth/rotas/org-selector/notificações/push) ou landing | `app-scaffold`                 |
| "Fica lento depois de X min" / "preciso dar F5" / memória cresce | `frontend-performance-audit`   |

## Telas canônicas — abra a reference ANTES de desenhar

Padronizadas em 2026-10-01 (código canônico = kailos, salvo onde indicado). Não reinvente por app.

| Tela / peça                                                         | Reference                                         |
| ------------------------------------------------------------------- | ------------------------------------------------- |
| Hub de configurações `?settings=` (empresa, membros, equipes, IA…)  | `references/settings-dialog.md`                   |
| Equipes (filas humanas do atendente de IA): grid de cards + editor  | `references/queues-editor.md`                     |
| Inbox WhatsApp `/chat` (conversas, janela, envio otimista, SSE)     | `references/whatsapp-inbox.md`                    |
| Config do agente de IA do tenant (Markdown + ChatGPT + versões; tools como permissões) | `references/agent-instructions.md` (template `agent-config/`) |
| Chat de IA streaming (`ai-elements/`) — o `chat/` de app é só ref.  | skill `ai-agents` → `frontend-chat.md`            |
| Documento imprimível / PDF                                          | `references/printing.md`                          |
| Vazio / erro / offline / confirmação / toast / skeleton             | `references/feedback-states.md`                   |
| Dashboard de KPIs (**reference, não obrigatório**)                  | `references/dashboard-kpi.md`                     |
| Casca: org-selector + `NewOrgDialog`, `can()` + `beforeLoad`, notificações, push, `/auth/login`, landing | skill `app-scaffold` |

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
  `references/list-options.tsx` + `references/list-pagination.tsx` +
  `references/use-collection-list.ts` + `references/use-infinite-list.ts` +
  `references/use-paged-list.ts` + `references/use-recently-opened.ts` — tela de lista
  (tabela↔card por role de coluna, modo por tela — rolagem contínua default, páginas no ⋮ —, totais
  no topo, "Abertos recentemente", busca/filtro/ordenação na URL, prefixo de query key que mantém a
  invalidação, scroll sem `IntersectionObserver`; mata `<Table>` sem card no mobile e `limit: 500`). Filtro de
  status com contagem por opção (`…/status-counts`) e ações em lote no menu `Ações` do toolbar
  (`references/bulk-actions-menu.tsx` + `references/use-list-selection.ts`).
- `references/agent-instructions.md` — config do agente de IA do tenant (Markdown único montado no
  ChatGPT por botão com pré-prompt do domínio, colado e mostrado renderizado + prévia; o que a
  plataforma injeta em runtime fica FORA do texto; versões com restaurar; tools como colunas de
  permissão no akmeo; template canônico `agent-config/`).
- `references/queues-editor.md` — Equipes: grid de cards + editor one-page (`FormDialog xl`, dados |
  membros com dnd-kit, rodapé Excluir/Salvar); kailos canônico, balizap alinha.
- `references/whatsapp-inbox.md` — inbox `/chat` do kailos (layout lista/janela, SSE keyed por ORG e
  nunca pelo contato ativo, envio otimista, tema `--wa-*`); nexarena adota sem equipes.
- `references/feedback-states.md` — `EmptyState`, erro≠vazio (`ErrorState`), `NetworkStatusBanner`,
  `ConfirmDialog` único, toasts, skeletons.
- `references/printing.md` — `PrintSheet` + `Doc*` + `PrintableDocumentDialog` + rota pública por token.
- `references/dashboard-kpi.md` — `PeriodSelector`/`StatCard`/`ui/chart.tsx` (reference opcional).
- `references/pwa-mobile.md` — PWA instalado no celular (`minimal-ui` vs standalone e por que o iOS
  ignora; afordância de recarga obrigatória via `invalidateQueries`; `useIsStandalone`/pull-to-refresh
  com as constantes reais; safe-area + `viewport-fit=cover`; metas apple-\*; checklist de manifest).
- `references/settings-dialog.md` — hub de Settings deep-linkado (kailos canônico: `sections-config`
  com `gate`+`render`, `?settings=`, anatomia `h-[calc(100dvh-2rem)] lg:max-w-[83rem]`, header com HelpButton nos dois
  tamanhos, nav com grupos+busca, mobile nav sobreposta, membros/convites, permission gating).
- `references/toggle-card.md` + `references/toggle-card.tsx` — ToggleCard (toggle boolean como card
  clicável; chip + liquid wash + beam sincronizado; tabela de decisão vs CardCheckbox/Switch residual; keyframes).
- `references/confirm-dialog.tsx` — ConfirmDialog (padrão ÚNICO de confirmação destrutiva: AlertDialog
  central, `busy` async; mata tira inline/accordion/button-swap/`window.confirm`). Doc na seção confirm de `overlays.md`.
- `references/file-upload.md` — padrão de UI de upload (dropzone, 2 fluxos de título, menu de ações,
  preview PDF/Office/imagem, progresso via XHR `useUploadMutation`/`UploadProgress`, `DocumentSlot`,
  variante "arquivos pendentes no form de criação", `useFileUpload`/`upload-error`/`file-types`
  canônicos). Espelha backend `uploads-storage`.
- `references/entity-picker.md` + `references/entity-picker.tsx` — EntityPicker (TODA FK em form
  como combobox pesquisável no servidor + quick-create "Novo…" que auto-seleciona; wrapper por
  entidade + `usePickerLabel`; regra "FK limpa" + `rg` de auditoria; contrato
  `useList`/`PagedResponse`+`search`; 3 adapters (CrudService / `useInfinitePages` / bounded), `Popover modal`, rodapé; mata Select estático e Input de ID cru).
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
