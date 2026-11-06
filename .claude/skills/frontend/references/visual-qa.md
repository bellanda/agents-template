# Seção nova grande: benchmark antes + QA visual em 3 larguras depois

Decisão do usuário (2026-11-05, durante o CRM 2030 do kailos): "sempre que faço novas seções
grandes, sempre tenho que ficar corrigindo bugs visuais". Daqui em diante, **quem constrói é quem
testa visualmente**: o agente abre a tela no navegador em celular, tablet e PC, olha os screenshots,
roda as checagens automáticas e corrige até ficar limpo, ANTES de entregar. Custa mais tempo; vale.

## Quando se aplica

| Situação | O que fazer |
|---|---|
| Rota/tela nova, redesign de tela, fluxo multi-tela, dialog grande novo (form com 2+ seções, hub, quadro/kanban, painel lateral) | **Benchmark + QA visual completos** (esta reference) |
| Ajuste de 1 componente, texto, cor, bug pontual | Só o item 10 do gate (mobile-first em 375px) |
| Auditoria de consistência de um app inteiro | `audit-checklist.md` (Modo 2) + o harness desta reference para as telas varridas |

## 1. Antes de construir: benchmark (~10 min)

1. **Padrão da tela.** Lista/CRUD · detalhe com abas · dashboard de KPI · quadro/kanban ·
   chat/inbox · wizard · hub de configurações · impressão.
2. **Abra o melhor exemplo da frota** do mesmo padrão:
   - o código canônico da tabela "Telas canônicas" do `SKILL.md`;
   - a **galeria** `/mnt/c/Users/gusta/OneDrive/Config Files/agents/gallery/<padrão>/` (PNG em 390 e
     1440 das melhores telas da frota; ver `gallery/README.md`).

   Padrão fora da galeria → capture a tela mais próxima com o harness do app (mock), em 390 e 1440,
   e olhe antes de desenhar.
3. **Contrato visual** (5 linhas, no plano ou no brief do subagente):
   - casca (`SidebarLayout` ou `SidebarChatLayout`);
   - overlay (Dialog, FormDialog, nenhum);
   - modo de lista;
   - o que colapsa no celular (tabela→card, abas→Select, colunas→1);
   - onde fica a ação principal.

## 2. Depois de construir: QA visual (obrigatório antes de entregar)

Harness por app em `frontend/e2e/visual/` (canônico: kailos). Os arquivos portáveis moram em
`references/visual-qa-harness/` e são copiados SEM edição:
- `checks.ts` (checagens), `visual-qa.spec.ts` (screenshots + rolagem do dialog), `build-report.ts`,
  `run.ts` (`bun run qa:visual`), `README.md` (uso, gotchas, como portar);
- `playwright-projects.ts`: o trecho a mesclar no `playwright.config.ts` (`VISUAL_GLOB` como
  `testIgnore` nos projetos funcionais, `VISUAL_LOCALE`, os 3 projetos) + a linha do script.

Só 2 arquivos são do app:
- `routes.ts`: exporta `ROUTES: VisualRoute[]` (id, path, `data`, `setup` que abre dialog/aba,
  `waitFor`) e `ORG_ID`;
- `fixtures.ts`: exporta `installVisualMocks(page, mode)` + `DataMode` (mock de pior caso em
  snake_case, montado sobre o `installApi` de `e2e/fixtures/session.ts`).

O spec só lê `APP.loginPath`/`APP.appShellControl` do `session.ts`, que todo app da frota já tem.

1. **Registre a tela nova** em `routes.ts`, com dados **realistas de pior caso**:
   - nome e modelo longos, valor `R$ 1.234.567,89`, 0 itens e muitos itens;
   - os estados que importam (dialog aberto, aba, vazio, erro).

   A tela entra no registro para sempre, como regressão.
2. **Rode** `E2E_PORT=<porta livre> bun run qa:visual`:
   - os projetos são `visual-mobile` (iPhone/WebKit 390×844), `visual-tablet` (820×1180) e
     `visual-desktop` (1440×900, sidebar aberta);
   - a saída fica em `frontend/test-results/visual/<rota>/<viewport>.png` e `report.json`/`report.md`.
3. **Checagens automáticas** (falha dura):
   - scroll horizontal no documento ou no `main`;
   - elemento visível além da largura do viewport;
   - rodapé ou botão principal do dialog fora da tela;
   - erro no console ou exceção na página.

   Avisos: alvo de toque menor que 40×40 no celular; sobreposição na linha do header/toolbar.
4. **Olhe cada PNG** com a ferramenta Read. O automático não pega tudo. Procure:
   - texto ou valor cortado;
   - toolbar ou abas em 2 linhas;
   - card espremido;
   - grid desalinhado ou buraco vazio;
   - espaçamento inconsistente com a tela de referência;
   - hierarquia confusa, botão principal escondido;
   - dialog alto demais;
   - teclado ou safe-area (quando der para simular).
5. **Corrija e rode de novo** até as checagens ficarem limpas e a passada visual não achar nada.
   Corrija pelas regras do gate: container query, `min-w-0`, FormDialog, DataList etc. Nunca
   `useIsMobile`.
6. **Relate** os caminhos dos screenshots finais e a lista do que foi corrigido, em uma linha por
   item.
7. **Galeria.** A tela virou o melhor exemplo do padrão? Copie o 390 e o 1440 para
   `gallery/<padrão>/<app>-<tela>-<largura>.png` e atualize `gallery/README.md`.

## Subagentes e paralelo

- O orquestrador põe o passo 2 no brief de **todo** subagente que constrói tela. O Sonnet lê PNG
  normalmente.
- Na revisão final, o orquestrador abre pelo menos o 390 e o 1440 de cada tela nova.
- Cada agente usa sua `E2E_PORT` (dev servers em paralelo não podem colidir). O `check.sh` continua
  serial e sem agente vivo.

## Modo LIVE (opcional)

`E2E_LIVE=1 E2E_LIVE_URL=… E2E_LIVE_EMAIL=… E2E_LIVE_PASSWORD=…` roda o mesmo registro contra um
stack **local**, sem mocks, para ver dado real. **Nunca contra prod.** Credenciais só por env, nunca
no repo.

## Gotchas

- Espere a rede assentar e os skeletons sumirem antes do screenshot (`waitForLoadState` + um
  seletor do conteúdo real). Screenshot de skeleton não testa nada.
- UI que depende de hora (SLA, contagem regressiva, "há 5 min") → `page.clock` fixo, senão o
  screenshot muda a cada execução.
- WebKit é obrigatório no celular: é o motor do iOS, o mais restritivo (zoom em input <16px,
  `100vh`, safe-area).
- O screenshot full-page esconde o problema de "rodapé fora da tela". Por isso a checagem do dialog
  mede o retângulo do viewport, não a página.
- **Locale do navegador.** `locale: "pt-BR"` só muda `Intl`/`navigator`. Input nativo de data/hora
  segue o locale do PROCESSO: no Chromium headless do Linux é a env `LANG`. Sem
  `LANG=pt_BR.UTF-8` o print mostra "08:00 AM" e "mm/dd/yyyy", que o usuário nunca vê
  (`VISUAL_LOCALE`, verificado em 2026-11-05).
- **Dialog aberto = print só do viewport.** Full-page com dialog mostra a lista vazando por baixo do
  overlay. A rolagem interna do dialog sai como `<viewport>-scroll-N.png`. O mesmo vale sem dialog
  quando o DOCUMENTO não rola e a página rola num container interno (casca do optimuslar,
  `flex-1 overflow-y-auto`): o full-page parava na dobra. App cujo documento rola não ganha shot
  extra (2026-11-05).
- **O mock espelha a API de verdade.** Telefone canônico (`5511987654321`, sem `+`), datas ISO com
  `Z`, snake_case. Mock "bonito" esconde bug: o valor cru no cabeçalho da conversa só apareceu
  quando o mock passou a mandar o canônico (kailos 2026-11-05). Leia o PNG procurando valor cru.
- **WebKit no WSL** deixa o XHR escapar do `page.route` (o mock não pega). O `visual-mobile` usa a
  emulação do Chromium por padrão; `VISUAL_WEBKIT=1` liga o WebKit real numa máquina que suporta.
- **Checkbox de 17px dentro de card clicável** (`CardCheckbox`) gera aviso de alvo de toque. É falso
  positivo: o alvo é o card inteiro.
- **Balão de onboarding intercepta clique.** Tela com `OnboardingBalloon` deve dispensá-lo ("Entendi") no
  `setup` da rota antes de interagir (cobre header/burger/menu do usuário e o clique estoura timeout).
  Ver `onboarding-balloon.md` (`dismissListBalloon` no kailos).
- **`getByRole('dialog')` é ambíguo com balão aberto**: o popover também é `role=dialog`. No strict
  mode o locator quebra; com `.first()` o desktop fotografou o balão como "superfície". Localize pelo
  slot (`[data-slot=form-dialog]`, `[data-slot=dialog-content]`).
- **Mock com shape errado derruba a tela no print.** Endpoint de coleção devolve `PagedResponse`
  (`{items,total,skip,limit,has_more}`), nunca `[]` cru: um `/members` mockado como lista solta deu
  "Cannot read properties of undefined (reading 'length')" e o print saiu com a tela de erro (kailos
  2026-11-05).
