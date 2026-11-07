# Estilos do app ("temas gerais") + base escura da frota

Fonte ÚNICA do sistema de estilos visuais escolhidos por pessoa. Kailos inventou o sistema em
2026-09. Em 2026-11-07 o usuário decidiu levá-lo a toda a frota: "não aplicar o modo de Temas
gerais em todos?". Na mesma data decidiu que o escuro de todo app usa a base do GitHub:
"essa cor de fundo do GitHub… digo apenas a cor base". Os CSS canônicos estão em
`app-styles/*.css`, ao lado deste arquivo.

## 1. PADRÃO vs IDENTIDADE (exceção decidida)

- **Padrão em todos os apps:**
  - os NEUTROS do escuro (`dark-base.css`): fundo, cards, controles, bordas, texto e moldura;
  - o mecanismo de estilos;
  - os 6 estilos genéricos.
- **Identidade, por app:**
  - `--primary*`, `--ring`, `--chart-*` e `--sidebar-primary*`;
  - o claro padrão (`<slug>-claro`);
  - os estilos de marca. Hoje só o kailos tem: Faixas, Laranja total, Promocar claro, Promocar e Petróleo noturno.
- O escuro "fosco" antigo (zinc/neutral do shadcn, `oklch(0.141 0.005 285)`) saiu de todos os apps.
- Quem queria um escuro quente tem o estilo **Carbono**.

## 2. Catálogo por app

| id | nome | modo | papel |
| --- | --- | --- | --- |
| `<slug>-claro` | "<App> claro" | light | **default**, identidade do app (o `:root` do index.css) |
| `nitido` | Nítido | light | neutros frios do GitHub claro, moldura gelo |
| `grafite` | Grafite | light | sidebar grafite + pílula da primária. Pule se o claro padrão já tem sidebar escura (akmeo). |
| `areia` | Areia | light | papel quente |
| `<slug>-escuro` | "<App> escuro" | dark | base GitHub (`.dark` do index.css) |
| `escuro-suave` | Escuro suave | dark | GitHub "dimmed" `#212830` |
| `carbono` | Carbono | dark | preto quente |
| `alto-contraste` | Alto contraste | dark | GitHub "high contrast" |

- `<slug>`: kailos, emporion, nexarena, akmeo, promoservice, optimuslar. No template é `app`, e o scaffold de um app novo renomeia.
- Os ids do kailos são fixos, porque já estão gravados em `users.ui_preferences` de prod.
- **Regra do catálogo:** o estilo já carrega o modo (não existe "claro + botão escuro").
- Todo id existe em TRÊS lugares, com um teste que os amarra:
  1. `lib/appearance/app-styles.ts`;
  2. o arquivo `styles/themes/<id>.css` (exceto o par de identidade, que é o `:root`/`.dark`);
  3. o `AppStyleId` (Literal) do backend.

**`themeColor`** (`<meta name="theme-color">`) é a cor do topo do estilo:

| Estilo | Cor |
| --- | --- |
| escuro (identidade) | `#010409` |
| Nítido | `#f6f8fa` |
| Escuro suave | `#151b23` |
| Alto contraste | `#010409` |
| Carbono | `#0b0a09` |
| Areia | `#fcfaf7` |
| Grafite | o hex do grafite tingido |
| claro (identidade) | a cor do header do app |

## 3. Contrato da base escura (`dark-base.css`)

Camadas, da mais escura para a mais clara:

| Camada | Token | Hex |
| --- | --- | --- |
| moldura | `--sidebar` | `#010409` |
| conteúdo | `--background` | `#0d1117` |
| card e popover | `--card` / `--popover` | `#151b23` |
| controles | `--secondary` / `--muted` | `#212830` |
| hover | `--accent` | `#262c36` |

- **Header** = moldura. A regra `[data-app-header] { background: var(--sidebar) }` vale no estilo escuro padrão.
- **Bordas:** `#3d444d` a 70%; o `--input` usa `#3d444d` cheio.
- **Texto:** `#f0f6fc`. O secundário é `#9198a1`, com 6,5:1 no conteúdo e 5,9:1 no card.
- **Regra para QUALQUER estilo escuro, novo ou revisto:**
  - a moldura é mais funda que o conteúdo;
  - o card se destaca do conteúdo;
  - o `--muted-foreground` tem ≥ 4,5:1 no card (alvo ~6:1);
  - a borda é visível sem gritar.
- **Cor crua de escuro quebra a base.** Exemplos: `dark:bg-zinc-900`, `dark:bg-neutral-950` e hex de fundo no componente. Ao aplicar, varra com `rg "dark:(bg|border)-(zinc|neutral|slate|gray|stone)-"` e troque pelos tokens.

## 4. Mecanismo (canônico: kailos)

| Peça | Arquivo kailos | Papel |
| --- | --- | --- |
| Catálogo | `frontend/src/lib/appearance/app-styles.ts` | `APP_STYLES` (id, name, mode, themeColor), `DEFAULT_APP_STYLE`, `isAppStyleId`, `findAppStyle` |
| Store | `frontend/src/lib/appearance/app-style-store.ts` | Ver detalhes abaixo da tabela. |
| Hook | `frontend/src/hooks/useAppStyle.ts` | `useAppStyle()` devolve `{style, mode, chooseStyle, previewStyle}`. `chooseStyle` aplica e faz `PATCH /accounts/me/ui-preferences {appStyle}`. Também: `useAppStyleChoicePending`, `useAppStyleMode`. |
| UI | `frontend/src/components/theme/AppStyleDialog.tsx`, `AppStylePicker.tsx`, `AppStylePreview.tsx` | Ver detalhes abaixo da tabela. |
| Link | `frontend/src/routes/_authenticated/estilo/$styleId.tsx` | `/estilo/<id>` aplica e segue para o dashboard. Roda no efeito, NUNCA no `beforeLoad`: o preload por hover trocaria o estilo. |
| CSS | `frontend/src/styles/themes/*.css` + `@import` no `index.css` | `surfaces.css` vem primeiro. Cada arquivo sobrescreve só o que difere. |
| Ganchos | `data-app-header` (header do shell), `data-settings-nav` / `data-settings-header` (hub), `data-kpi-card` / `data-kpi-icon` (StatCard), `data-sidebar` (shadcn) | Os estilos pintam a moldura por eles. Portar o sistema = pôr os ganchos nos componentes. |
| Toaster | `components/ui/sonner.tsx` | O tema do toast vem de `useAppStyleMode()`, não do `ThemeProvider`. |
| Backend | migration `users.ui_preferences jsonb NOT NULL DEFAULT '{}'`, `schemas/accounts/accounts.py` (`AppStyleId` Literal + `UiPreferencesUpdate`), `user_repository.set_app_style` (`jsonb_set`, sem apagar outras chaves), `routes/accounts/accounts.py` `PATCH /accounts/me/ui-preferences` | `/accounts/me` devolve `ui_preferences`. Teste: `backend/tests/accounts/test_ui_preferences.py`. |

- **Store:**
  - `<html data-style class="light|dark">` + a meta theme-color;
  - cache em localStorage (`<slug>:app-style:v1`), pintado em `bootAppStyle()` no `main.tsx` antes do 1º render;
  - `syncFromAccount` segue `authStore.user.uiPreferences.appStyle` e só reaplica quando o valor DA CONTA muda;
  - `markAppStyleChosen` grava o id do usuário, não um booleano.
- **UI:**
  - O botão paleta (`LuPalette`, "Estilo") no header do desktop + o item "Estilo" no `HeaderOverflowMenu` do celular substituem o `ThemeToggle`.
  - O dialog tem prévia ao vivo (aplica no documento inteiro enquanto navega) e radiogroup em 2 grupos, Claros e Escuros, com miniatura via `data-style-preview`.
  - Rodapé: "Usar <nome>". Fechar confirma.
  - `AppStyleWelcomeDialog` abre no 1º acesso de quem não tem `app_style`.
- **Prévia por domínio:** a `AppStylePreview` é uma mini-casca com o menu, os KPIs e a lista DO APP, com os mesmos ganchos. Nunca copie os veículos do kailos.

## 5. Gotchas

- **Legado do `ThemeProvider`.** Na 1ª carga sem o cache novo, leia UMA vez a chave antiga (`vite-ui-theme` ou a do app).
  - `dark` vira `<slug>-escuro`; o resto vira o default.
  - Depois remova a chave antiga.
  - Assim quem já usava escuro não volta ao claro.
- **Boas-vindas só na casca de trabalho.**
  - Tela operacional em tela cheia ou kiosk (cozinha, motoboy, TV, impressão, rota pública por token) nunca abre o dialog de boas-vindas. Um tablet da cozinha não pode ficar travado num popup.
  - Esse dialog e o "Como funciona" (quando o app tem) não abrem juntos; o kailos segura a ajuda até o estilo fechar.
- **Páginas públicas** (landing, login) seguem o cache local; sem cache, o default. Não há seletor nelas.
- **Prévia ≠ escolha.** `previewStyle` pinta sem gravar. Fechar o dialog confirma o estilo em prévia; o PATCH só sai no confirmar.
- **E2E/QA visual.** O fixture de sessão leva `ui_preferences: { app_style }`. Uma rota de QA por estilo relevante: o dialog aberto, o dashboard no escuro padrão e um estilo genérico, a 390 e a 1440.

## 6. Testes mínimos (por app)

- pytest:
  - PATCH com id válido grava e volta em `/accounts/me`;
  - id inválido dá 422;
  - o PATCH não apaga outras chaves de `ui_preferences`.
- vitest:
  - catálogo × CSS: todo id não-identidade tem `styles/themes/<id>.css` importado no `index.css`;
  - catálogo × backend: lista de ids igual ao Literal (snapshot do array);
  - store: boot pinta o cache, migra a chave legada `dark`, e conta que muda reaplica.
