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
| Hook | `frontend/src/hooks/useAppStyle.ts` | `useAppStyle()` devolve `{style, mode, chooseStyle, previewStyle}`. `chooseStyle(id, fontSize?)` aplica e faz `PATCH /accounts/me/ui-preferences {appStyle, fontSize}`. Também: `useFontSize`, `useAppStyleChoicePending`, `useAppStyleMode`. |
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
  - O botão paleta (`LuPalette`, title "Aparência") no header do desktop + o item "Aparência" no `HeaderOverflowMenu` do celular substituem o `ThemeToggle`.
  - O dialog segue o §8: opções à esquerda, área "Exemplo" à direita, prévia ao vivo no documento inteiro, radiogroups de letra, Claros e Escuros, miniatura via `data-style-preview`.
  - Rodapé: "Salvar". Fechar confirma.
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

## 7. Tamanho da letra (decisão do usuário 2026-11-09)

Motivo: "a letra é importante para pessoas que reclamam estar pequenas as letras". Mora no mesmo
dialog dos estilos e no mesmo `ui_preferences`, sem migration.

| id | nome | escala |
| --- | --- | --- |
| `padrao` | Padrão | 100% (default) |
| `grande` | Grande | 112,5% |
| `muito-grande` | Muito grande | 125% |

- **Mecanismo:** `<html data-font-size="<id>">` define `--app-font-scale` (`app-styles/font-size.css`, canônico, importado no `index.css` depois dos estilos), e o `html` do `index.css` faz `font-size: calc(17px * var(--app-font-scale, 1))`. Quem não fixa 17px usa `calc(100% * var(--app-font-scale, 1))`.
- **Por que no `<html>`:** o Tailwind mede texto, espaçamento e ícone em `rem`, então a tela inteira cresce junto, como o zoom do navegador, sem texto grande em caixa apertada. Container queries em `rem` acompanham a escala; media queries não (usam o tamanho inicial do navegador).
- **Peças:** `lib/appearance/font-size.ts` (catálogo + store: cache `<slug>:font-size:v1`, `bootFontSize()` no `main.tsx`, `syncFromAccount`), `useFontSize()` em `useAppStyle.ts`, backend `FontSizeId` (Literal) + `font_size` opcional no PATCH + `user_repository.set_font_size`.
- **Só para cima.** Nunca crie degrau abaixo de 100%: os campos cairiam para menos de 16px e o iOS daria zoom ao focar (`ios-input-zoom.test.ts`).
- **Teto em 125%.** Num celular de 390px isso equivale a uma tela de ~310px, o limite em que os layouts ainda respiram.
- **Texto SEMPRE em `rem`.** `text-[11px]` não cresce com a preferência, e é justamente a letra menor. Use `text-[0.6875rem]` (px ÷ 16). Exceções: `text-[0px]` e documento impresso (`components/print/`). O teste `font-size.test.ts` barra `text-[Npx]` novo.
- **Gráficos:** o Recharts grava `font-size` como atributo SVG; o `font-size.css` escala `.recharts-text` só nos tamanhos maiores.
- **Impressão:** `@media print` volta a escala para 1. A preferência é de tela.
- **Prévia ≠ escolha:** como no estilo, `previewFontSize` pinta sem gravar; o PATCH sai no confirmar, junto do estilo (`chooseStyle(style, fontSize)`).
- **Testes mínimos:** vitest `font-size.test.ts` (catálogo × CSS × Literal do backend, boot pinta o cache, conta que muda reaplica, nenhum `text-[Npx]`); pytest grava `font_size`, não apaga outras chaves, id inválido dá 422.

## 8. Layout do dialog (decisão do usuário 2026-11-09, inspirado no Shadcn Create)

O dialog é uma tela de configuração, e o que está ao lado é só amostra.

- **PC:** `FormDialog size="2xl"` (largura do hub de configurações) com `className="h-[calc(100dvh-2rem)]"` e `bodyClassName="@3xl:overflow-hidden @3xl:p-0"`. A partir de `@3xl` (largura do próprio dialog, que acompanha a letra) são duas colunas com rolagem própria: painel de opções (18rem) e área de exemplo. Abaixo disso, coluna única com a rolagem do corpo.
- **Painel de opções:** primeiro "Tamanho da letra" (3 botões com um "A" crescente), depois Claros e Escuros em coluna única.
- **Área de exemplo:** fundo `bg-muted/40`, selo "Exemplo" + frase dizendo que nada ali funciona de verdade. O conteúdo fica em `inert` (sem foco nem clique, nenhum controle parece real).
- **Conteúdo do exemplo:** `AppStylePreview` (mini-casca com o domínio do app, §4) + `AppStyleSamples` (componentes shadcn genéricos, igual em todos os apps: texto, botões, formulário, etiquetas). Grade `repeat(auto-fill,minmax(min(100%,14rem),1fr))`, que se ajusta sozinha ao tamanho da letra.
- **Celular:** coluna única nessa ordem (letra, estilos, exemplo); "Salvar" fica sempre visível no rodapé do `FormDialog`.
- **Nome:** o dialog chama "Aparência", porque cuida de cores E letra. Os ids e rotas `estilo` não mudam.
