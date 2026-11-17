---
paths:
  - "**/tests/**"
  - "**/test_*.py"
  - "**/conftest.py"
  - "**/*.test.{ts,tsx}"
  - "**/__tests__/**"
  - "**/e2e/**"
  - "**/playwright.config.*"
  - "**/src/test/**"
---

# Backend Testing

> **Política (decisão do usuário 2026-10-15):** testes são parte da entrega, sem precisar de pedido.
>
> 1. **Bug corrigido → teste de regressão** que falha sem o fix (reproduz o cenário real do incidente).
> 2. **Funcionalidade principal/crítica** (auth, tenancy, dinheiro, webhook/integração, envio de mensagem, migrations
>    com dado) → testes **consolidados e equilibrados**: poucos arquivos, cenários densos de ponta a ponta + bordas.
> 3. **Demais funcionalidades** → cobertura razoável (caminho feliz + falha mais provável).
>    Proibido teste especulativo, duplicado ou que só espelha a implementação. Siga o formato rápido abaixo
>    (xdist, banco por worker, NATS real) — é o que deixa a suíte inteira em ~2 min.

## Agent-runnable first

- Suite roda com **um comando documentado** (`uv run pytest`, `make test`). Sem seed manual, sem credentials escondidos, sem prompt interativo.
- Output parseável: pass/fail no stdout. Sem TTY dependency.
- Setup novo → documenta em `CLAUDE.md`/`AGENTS.md`/`README.md` do projeto.

## F.I.R.S.T

**Fast** (segundos) | **Independent** (qualquer ordem passa via rollback ou DB ephemeral) | **Repeatable** (determinístico — unique data para `UNIQUE` fields) | **Self-validating** (assertions explícitas, sem "olha o log") | **Timely** (junto com o código — bug fix = regression test).

### Repeatable inclui o CALENDÁRIO — relógio e data são um PAR

**Canário de fuso (padrão da frota, 2026-11-06):** a suíte roda com o processo pytest e o Postgres
de teste em `Pacific/Kiritimati` (UTC+14: `TEST_TIMEZONE` + `time.tzset()` no topo do conftest e
`-c timezone=` no `tests/compose.yml`). Lá a data local difere da de São Paulo das 07h às 24h, então
dia calculado no fuso do servidor falha em horário de trabalho em vez de só à noite. Teste que quebra
com o canário é bug (de teste ou de produção), nunca motivo para tirar o canário. Trava estática +
canário: gate `database` → `local-time.md`.

Todo teste que envolve tempo tem dois lados: o **dado** (a data semeada) e o **relógio** (o que o código chama de "agora"). Só existem duas combinações válidas, e a mistura das duas é a que apodrece:

| Combinação                       | Como                                                           | Quando usar                                                                                   |
| -------------------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| **Relógio fixo + dado fixo**     | injeta `now=`/`evaluated_at=` na função e crava a data literal | a função sob teste **aceita** o relógio (função pura, job, service com parâmetro)             |
| **Relógio real + dado relativo** | `dt.datetime.now(dt.UTC) ± dt.timedelta(...)`                  | o serviço lê `now()` **por dentro** e a rota não expõe injeção — aí o único controle é o dado |

**PROIBIDO: data absoluta + relógio real.** Passa hoje, falha num dia específico do futuro, e o culpado parece ser a mudança em curso — não o teste escrito meses antes. Já aconteceu duas vezes: 63 testes caíram quando a largada cravada em `2026-09-01` entrou no prazo de 3 dias antes da prova, e um teste de métricas quebrava **toda segunda-feira** (semeava "ontem" e exigia que ontem estivesse dentro da semana corrente, que na segunda começa hoje).

- Janela de calendário (`wtd`/`mtd`, "semana atual", "mês até hoje") tem **fronteira**: semear "ontem" e afirmar pertencimento falha na segunda-feira e no dia 1º. Se o relógio for fixo, escolha uma referência **longe das bordas** (meio de semana, meio de mês) e **no passado**.
- **Cravar um lado só não resolve.** Se a fixture semeia pelo relógio real e o teste consulta com um `now` fixo (ou vice-versa), os dois lados divergem — pin nos DOIS ou em nenhum.
- **Acoplamento indireto**: dado relativo muda o **ano**. Constante derivada de ano (faixa etária, competência, exercício fiscal, safra) tem que derivar do MESMO lugar, senão o teste continua passando medindo outra coisa — falha silenciosa, pior que vermelho.
- Data absoluta em par casado (`DEFAULT_EVAL_AT` + `DEFAULT_EVENT_START_AT`, ambos injetados) é **correta e deve continuar absoluta**: comente o porquê, ou alguém "conserta" e cria a falha que não existia.

## Velocidade da suíte — paralela por padrão (decisão 2026-10-13)

- **pytest roda em paralelo** (`pytest-xdist`, `-n min(nproc, 8)` no `check.sh`; `--serial`/`PYTEST_WORKERS=0` = escape). Kailos: 4.682 testes de ~15 min para ~2 min.
- **Mesma major de produção nos testes** (2026-11-15): o Postgres de teste vem do `backend/tests/compose.yml` com a MESMA tag do `compose.yaml` (só o kailos tem a trava `tests/test_infra_versions.py`, que confere as tags de compose/backup/nginx; o template tem `backend/tests/scripts/test_infra_pins.py` (tabela única `PINS` de postgres/valkey/nats/dbmate/pgbouncer/bun/nginx/python: qualquer tag fora da tabela falha); nos demais apps nada trava: bump de major = conferir `tests/compose.yml` à mão). O Valkey de teste é o binário `valkey-server` do host, um por worker: tem de ser da major de produção (hoje 9.x em `~/.local/bin/valkey-server`, extraído da imagem `valkey/valkey:<tag>`; o do apt é 7.2 e não vale). Subiu a major no compose → troque o binário no mesmo trabalho.
- **Banco por worker**: o controller do xdist roda `dbmate up` UMA vez em `test_<app>_template`; cada worker clona `CREATE DATABASE test_<app>_<gwN> TEMPLATE …` (Valkey socket e app yaml também por worker, sufixo idempotente). Teste que commita de verdade em conexão própria é seguro porque o banco é do worker. NUNCA hardcode nome/DSN do banco de teste — importe `TEST_DATABASE_DSN` do `tests.conftest`.
- **Uma conexão por processo**: `db_conn` reusa a conexão da sessão (`_shared_test_connection()`), cada teste numa transação com rollback + `conn.reset()`; reconecta se o teste a fechou. Abrir conexão por teste (~18ms de SCRAM+fork) era mais da metade do tempo da suíte.
- **Postgres de teste** (`tests/compose.yml`): `autovacuum=off` (com ele, estatísticas do template/clones viravam o plano e um cenário longo travava — 3/5 runs paralelos estouravam), `fsync=off`, `synchronous_commit=off`, `full_page_writes=off`, `max_connections=300`. Só no DB efêmero de teste.
- `nats-server` do teste roda pelo binário do venv (não `uv run`, o SIGTERM não chega e pendura 5s). Sem `dbmate drop` no teardown (a sessão seguinte já dropa).
- Teste de lógica pura no front: `// @vitest-environment node` (jsdom custa ~40% do vitest). Espera de evento assíncrono = sinal (sentinela/NOTIFY), nunca `sleep` fixo.
- **Coleta determinística** (xdist exige a MESMA lista de testes em todo worker): `parametrize` com valor não determinístico (bytes de PDF/imagem gerados, datas, uuid) precisa de id estável — o hook `pytest_make_parametrize_id` do conftest canônico já dá id fixo a qualquer `bytes`; para outros tipos use `pytest.param(..., id="…")`. Senão o id muda por worker e a suíte aborta com "Different tests were collected" (optimuslar, 2026-10-13).
- Canônico: kailos `backend/tests/conftest.py` + `backend/tests/compose.yml` + `check.sh`.

## Scope

- **Integration-first via HTTP.** Testa comportamento observável pelo public interface.
- **Unit tests só para lógica pura, sem I/O.** Se integration cobre, não duplica.
- **DB de teste real** para persistência/queries/transactions/constraints/serialization/permissions. NUNCA mock DB.
- **NATS real nos testes, com os métodos reais do nats-py** (decisão do usuário 2026-10-14): o
  `nats-server` da sessão + `get_js()` de verdade; publica, roda o consumer e assere no estado do
  JetStream. PROIBIDO duplo de JetStream/subscription escrito à mão ou módulo `nats_client` falso
  espelhado: ele aceita qualquer método e o teste passa com chamada que não existe (kailos
  2026-10-14: `js.update_consumer` não existe no nats-py 2.16, os testes passaram e o consumer caiu
  em loop no deploy). Injeção de falha de broker que o servidor real não produz sob demanda = wrapper
  que DELEGA tudo ao objeto real (`__getattr__`) e sobrescreve só a chamada que falha. Caminho de
  migração de estado (durable antigo ganhando filtro novo, stream existente) tem teste que cria o
  estado antigo no NATS real antes. Atualizar durable = `add_consumer` com o mesmo nome (é o
  update no servidor); `update_consumer` não existe.
- Reutiliza fixtures shared (client, auth, base data). Sem recriar setup pesado por arquivo.

## Guardas estáticas e fixtures da frota (2026-11-13)

Copiadas sem edição do central (`skills/database/references/tenancy/` e `local-time/`) para todo
backend (exceto `test_tenancy_guard.py` em app sem `organization_id` no schema, como optimuslar: ele dá SKIP
se o schema não tem tabela de tenant, então ali o arquivo não existe): `test_tenancy_guard.py` (todo `.py` de `src`/`cron`/`pipelines`/`agents`/`scripts`: SQL em tabela
com `organization_id` ou em filha dela por FK filtra por ela ou leva `tenant-ok: <motivo específico>`), `test_client_ip_guard.py`,
`test_timezone_guard.py`, `core/test_streaming_routes_no_get_conn.py`; por app também
`tests/scripts/test_runtime_infra_config.py` (ajuste `APP_LIMIT_CAP_MB`/`MAX_GRANIAN_WORKERS` quando o
orçamento mudar de propósito) e `tests/test_fk_indexes.py`. Guarda vermelha = corrija o código; allowlist
só com motivo e dono.

- **Concorrência real** (duas requisições disputando o mesmo saldo/parcela) usa fixture com dado
  COMMITADO e conexão do pool por request (promoservice `tests/conftest.py` `race_env`, limpa org e
  usuário no teardown); o `client` padrão fixa uma conexão com rollback e não enxerga a corrida.
- **`updated_at` antigo em tabela `agent_*`**: o trigger BEFORE UPDATE reseta o valor; envelheça com
  `session_replication_role = replica` (`tests/helpers/aging.py`).
- **Handler dentro de task group do anyio**: exceção de domínio chega embrulhada em `ExceptionGroup`;
  capture com `except*` (skill `anyio-concurrency`), senão o `except` específico nunca casa.
- **Cron com constante Python**: o cron job que precisa de uma constante do `api.*` a espelha em
  `cron/settings.py` (a imagem do cron não tem `api`).

## Structure

- Arquivos `test_*.py`, funções `test_*`, classes `Test*` só para agrupar flow/resource.
- Arrange / Act / Assert minimalista. Direct assertions.
- Validação em ordem: `status_code` → main response body → side effects persistidos.

## Coverage por rota (mínimo)

| Caso                                       | Status                                                           |
| ------------------------------------------ | ---------------------------------------------------------------- |
| Success path                               | 200/201                                                          |
| Auth ausente/inválido                      | 401 (se aplicável)                                               |
| Permissão insuficiente                     | 403 (se aplicável)                                               |
| Resource não encontrado                    | 404 (se aplicável)                                               |
| Recurso de OUTRA org (GET/PATCH/DELETE)    | 404 — tenancy em toda rota por id, não só na transição de status |
| Payload inválido / business rule violation | 400 / 409 / 422                                                  |
| Empty result em list/search                | 200 + empty list                                                 |

**Guarda "toda rota de escrita tem teste que deu certo"** (auditoria de CRUD 2026-11-17, incidente
QUB5J53):

- **O que é:** plugin `tests/write_route_coverage.py` (canônico em `shared-backend/`, byte-idêntico,
  com autoteste `tests/test_write_route_coverage.py`), ligado por `pytest_plugins` no `conftest.py`.
- **O que conta:** só resposta 2xx/3xx em POST/PUT/PATCH/DELETE. Teste que só recebe 403/422 não
  prova que a escrita funciona.
- **Modos (`WRITE_ROUTE_COVERAGE`):**
  - o `check.sh` roda `enforce`: falha com rota nova sem teste e com linha da baseline que ganhou
    teste ou sumiu, então a baseline só encolhe;
  - `report` só lista;
  - `update` reescreve `tests/write_route_coverage_baseline.json`;
  - sem a variável, o plugin não faz nada.
- **Baseline:** cada linha leva um motivo de verdade (ex.: "OAuth do Google: precisa do código real,
  coberto por X"). Nunca "pendente".

**Matriz de CRUD por recurso**, um cenário denso por operação, relendo pelo `GET` que a tela usa
(regra "Escrita → releitura pelo que a TELA lê" abaixo):

- **Create:** depois do `POST`, o detalhe e a lista mostram os campos enviados.
- **Update:**
  - muda todo campo editável, e o `GET` mostra o valor novo;
  - a resposta do PATCH é igual ao `GET` do detalhe (o `useCrud` põe a resposta direto no cache da
    tela);
  - todo caminho extra que grava a mesma coluna (ação aprovada, import, sync, cron) tem o seu
    teste.
- **Delete:** o detalhe dá 404 e o item some da lista. No soft-delete, o item não volta.
- **Bordas:** a tabela acima (outra org = 404, sem permissão = 403, inválido = 422).

## Assertions — business outcomes

- Confirme business outcomes: status transitions, dados criados/updated, history, calculations, permissions, associations.
- **Nunca valide só formato.** "Response tem chave `users`" não é teste.
- Verifique error messages/codes no nível necessário para proteger o contrato. Não acople em texto frágil.
- Garanta que campos sensíveis nunca vazam (passwords, hashes, private tokens, internal secrets).
- **Escrita → releitura pelo que a TELA lê** (decisão do usuário 2026-11-17, incidente QUB5J53 no
  kailos). Teste de escrita (POST/PATCH/PUT, ação aprovada, import) relê o valor pelo endpoint de
  onde a tela o mostra: o `GET` do recurso, o resumo, o relatório. A resposta do próprio PATCH não
  conta, porque devolve o que ele mesmo gravou.
  - No incidente, o teste do PATCH passou com o carro em R$ 87.900 e o Desfecho em R$ 47.900.
  - Valor gravado por N caminhos (rota direta, ação aprovada, importação, sync) = um teste por
    caminho, cada um relendo por todas as telas que mostram o valor.
  - Canônico: kailos `tests/approvals/test_closed_deal_showroom_price.py`. Regra irmã:
    "Um valor, um lugar" em `backend.md`.

---

# Frontend Testing (Vitest)

> Testes fazem parte da entrega (decisão do usuário 2026-10-15): bug corrigido ganha teste de
> regressão; tela de CRUD ganha o teste de tela abaixo.

## Stack canônica

- **Vitest 4 + @testing-library/react + jsdom + bun.** Sem jest-dom/user-event/msw por default.
- Config no bloco `test:` do `vite.config.ts` (`defineConfig` importado de `vitest/config`):
  `environment: "jsdom"` · `globals: true` · `setupFiles: ["./src/test/setup.ts"]` (cleanup do
  testing-library) · `css: false`. Plugin tanstackRouter com `routeFileIgnorePattern: "__tests__"`.
- Script `"test": "vitest run"`; entra no `check.sh` como step antes do build.
- Imports explícitos de `"vitest"` (`describe, it, expect, vi`) mesmo com `globals: true`.
- **vitest 5** marca o teste como falho quando um mock `vi.fn()` devolve promise REJEITADA, mesmo que o app trate o erro. Teste que rejeita request usa função comum como stub (ver kailos `routes/__tests__/public-routes.test.tsx`).
- **Guardas de frontend na frota**: `data-list-layout.test.tsx` (idêntico nos 6 apps), `lib/api/__tests__/no-raw-fetch.test.ts`, `ios-input-zoom.test.ts`, `timezone-guard.test.ts`, `pwa-contract.test.ts`, `lib/api/__tests__/mutation-refresh-guard.test.ts` (2026-11-17: toda `useMutation` atualiza a tela; `invalidateQueries` com chave à mão só diminui; baseline em `src/test/mutation-refresh-baseline.json`).

## Onde moram

- Co-localizado (`dates.test.ts` ao lado de `dates.ts`) para 1–2 arquivos; `__tests__/` quando há
  vários testes do mesmo feature/diretório.

## Scope

- **Lógica pura sem I/O** → unit `.test.ts` sem React: utils, stores vanilla pub/sub (via
  `subscribe`/getters), zustand (via `getState()`/`setState()`, `localStorage.clear()` no beforeEach).
- **Componentes** → comportamento observável pelo usuário (o que aparece/acontece em interação),
  NUNCA implementação (className, estrutura DOM interna).
- Queries role-first: `getByRole` > `getByLabelText` > `getByText`; `getByTestId` é last resort;
  NUNCA `querySelector`.
- **Tela que GRAVA (CRUD) → fake de API com memória, nunca mock de hook** (auditoria de CRUD
  2026-11-17). O mock de hook esconde as duas falhas que mais aparecem: a tela que não atualiza
  depois de salvar e o formulário preenchido pela fonte errada (metade de frontend do QUB5J53).
  - **Ferramentas:** `src/test/fake-api.ts` (canônico, shared-widgets) + `src/test/crud-world.ts`
    do app, que liga o fake ao `useDataProvider` via `vi.mock("@/lib/api/context")`.
  - **Como o fake funciona:** as coleções REST guardam o que a tela grava (o `GET` seguinte
    devolve o valor novo); `fail("PATCH /x/:id", fakeApiError(409, …))` simula erro; `bodyOf`
    confere o corpo enviado.
  - **Cache igual ao do app:** o teste usa `createAppQueryClient()` (`lib/api/query-client.ts`,
    `staleTime` 30 s), nunca `new QueryClient()`. Com `staleTime` 0 toda tela remontada refaz a
    busca e esconde a invalidação que falta; em produção, quem volta à lista em < 30 s vê o cache
    velho (achado na rodada 2 da auditoria, 2026-11-17).
  - **Exemplo canônico:** kailos `components/contacts/__tests__/contacts-crud.test.tsx`, que monta
    a rota real com o router de memória.
  - **Roteiro por recurso, num teste denso:**
    1. a lista mostra o que está no fake;
    2. **criar:** o corpo do POST está certo (vazio = `null`, zero = `0`) e o item aparece na lista
       sem ajuste à mão no teste;
    3. **editar:** o formulário abre com o valor que a TELA mostra; depois de salvar, o corpo do
       PATCH está certo e toda parte da tela que mostra o valor mostra o novo;
    4. **excluir:** o item some;
    5. **erro 409/403:** o dialog fica aberto com o que foi digitado e nada muda;
    6. **sem permissão:** o botão some.
  - **Prova:** tire a invalidação da mutation por um instante e confira que o teste falha.
- Mock de hook (`vi.mock("@/hooks/useX", ...)`) + `vi.clearAllMocks()` no `beforeEach` só para
  componente que não grava (exibição, filtro). Sem msw.
- Componente que usa `useSearch`/`useNavigate`/`useQuery` → harness `renderWithProviders`
  (`src/test/test-utils.tsx`): QueryClient retry-off + router de memória real
  (`createMemoryHistory` + `createRootRoute`); URL assertada via `router.state.location.search`;
  `initialSearch` simula F5 com param na URL.
- **NÃO testar:** tipos (compilador cobre), componente dumb sem lógica, integração com API real.

## Sessão (auth) — harness dedicado

- `src/test/auth-harness.ts` é o kit de sessão, compartilhado por toda suíte de auth:
  `mockJwt({ expiresInSeconds })` (access com `exp` real — é assim que se simula TTL de 5s/10s),
  `installFetchMock(routes)` (fila de respostas por rota + `delayMs` para rede lenta +
  `networkError`; a rota mais específica vence, então `/auth/token/logout` ≠ `/auth/token`),
  `mockWebLocks()`, `mockDisplayMode(installed)`, `resetSessionState()`.
- **`mockWebLocks()` é obrigatório em teste de concorrência de refresh**: jsdom NÃO tem
  `navigator.locks`, então `withRefreshLock` cai no fallback e o teste passa por acidente.
- Refresh se prova pelo **contador de chamadas a `/auth/token`** (N requests em 401 → 1 refresh),
  nunca por espionar método interno. Concorrência real usa **instâncias distintas do ApiClient**
  (o dedupe de instância mascara a falta do lock).
- `waitFor` do testing-library faz polling com timer REAL → trava sob `vi.useFakeTimers()`.
  Com fake timers use `await act(async () => { await vi.advanceTimersByTimeAsync(n) })`.
- TTL curto no backend não precisa de branch de teste: `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` é float
  (`0.0833` = 5s, `0.1667` = 10s).

## E2E (Playwright)

- **Quando E2E e não unit:** o que só existe no browser real — manifest servido de verdade, metas
  do iOS, geometria no viewport do aparelho, safe-area/notch, gesto de pull-to-refresh, teclado do
  iOS, offline de verdade. Todo o resto é vitest (mais rápido e determinístico).
- Stack: `@playwright/test`, specs em `frontend/e2e/`, dois projects — `iphone`
  (`devices["iPhone 15"]`, **WebKit**) e `android` (`devices["Pixel 7"]`, Chromium). WebKit é
  obrigatório: o iOS é o ambiente mais restritivo e o que ignora `minimal-ui`. No Linux ele exige
  libs de sistema (`sudo npx playwright install-deps`); sem elas só o project `android` roda.
- **Backend mockado na rede**, não de pé: `installApi` (`e2e/fixtures/session.ts`) intercepta
  `**/api/v1/**` e responde a tudo — sem docker, sem DB e sem depender do login do Google, que não
  é automatizável. O glob PRECISA do `v1`: `**/api/**` também casa os módulos servidos de
  `src/lib/api/*.ts` em dev, e o app carregaria JSON no lugar do próprio código.
- `webServer` sobe o dev server com `VITE_BACKEND_URL` na **própria origem** — same-origin evita o
  preflight de CORS, que o interceptor de rota não cobre.
- Offline é `setOffline` do próprio mock (`route.abort`), NUNCA `context.setOffline`: o request
  interceptado não chega à pilha de rede e continuaria respondendo.
- `page.clock.install()` + `fastForward` para cruzar o limiar de resume (~60s) — esperar em tempo
  real inviabiliza a suíte. O TTL do access vem do `exp` do JWT mockado.
- O que diverge por projeto mora SÓ no `fixtures/session.ts` (rota home, payload do `/accounts/me`,
  quantas chamadas o bootstrap gasta); os specs são idênticos em todos os apps da frota. Rota home = tela de lista que
  aguenta `PagedResponse` vazio — dashboard que depende de payload de KPI quebra no mock.
- **Spec que mede a tela espera a tela, nunca um tempo fixo.** Depois do `goto`: casca visível
  (`APP.appShellControl`, timeout ~30s — Vite frio + vários workers demoram), `networkidle` com teto
  (`.catch` — tela com polling/fotos nunca fica ociosa) e um marcador do conteúdo (h1 do header não
  vazio). `waitForTimeout` sozinho fotografa o spinner/página em branco e a asserção de layout passa
  sem medir nada (varredura de layout, 2026-10-09: dezenas de rotas "verdes" em branco). Screenshot
  de poucos KB = sinal de teste vazio.
- Script `"test:e2e": "playwright test"` — **fora do `check.sh` padrão** (sobe dev server + 2
  browsers); entra em alvo próprio (`bash check.sh --e2e`) para não tornar o check local lento.
