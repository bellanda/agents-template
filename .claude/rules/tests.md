# Backend Testing

> Aplica-se **quando o user pede** para escrever/rodar testes ou para criar regression test do bug que está sendo corrigido. Não escreva testes especulativos (ver `agent-behavior.md > Restrictions`).

## Agent-runnable first

- Suite roda com **um comando documentado** (`uv run pytest`, `make test`). Sem seed manual, sem credentials escondidos, sem prompt interativo.
- Output parseável: pass/fail no stdout. Sem TTY dependency.
- Setup novo → documenta em `CLAUDE.md`/`AGENTS.md`/`README.md` do projeto.

## F.I.R.S.T

**Fast** (segundos) | **Independent** (qualquer ordem passa via rollback ou DB ephemeral) | **Repeatable** (determinístico — unique data para `UNIQUE` fields) | **Self-validating** (assertions explícitas, sem "olha o log") | **Timely** (junto com o código — bug fix = regression test).

## Scope

- **Integration-first via HTTP.** Testa comportamento observável pelo public interface.
- **Unit tests só para lógica pura, sem I/O.** Se integration cobre, não duplica.
- **DB de teste real** para persistência/queries/transactions/constraints/serialization/permissions. NUNCA mock DB.
- Reutiliza fixtures shared (client, auth, base data). Sem recriar setup pesado por arquivo.

## Structure

- Arquivos `test_*.py`, funções `test_*`, classes `Test*` só para agrupar flow/resource.
- Arrange / Act / Assert minimalista. Direct assertions.
- Validação em ordem: `status_code` → main response body → side effects persistidos.

## Coverage por rota (mínimo)

| Caso                                       | Status             |
| ------------------------------------------ | ------------------ |
| Success path                               | 200/201            |
| Auth ausente/inválido                      | 401 (se aplicável) |
| Permissão insuficiente                     | 403 (se aplicável) |
| Resource não encontrado                    | 404 (se aplicável) |
| Payload inválido / business rule violation | 400 / 409 / 422    |
| Empty result em list/search                | 200 + empty list   |

## Assertions — business outcomes

- Confirme business outcomes: status transitions, dados criados/updated, history, calculations, permissions, associations.
- **Nunca valide só formato.** "Response tem chave `users`" não é teste.
- Verifique error messages/codes no nível necessário para proteger o contrato. Não acople em texto frágil.
- Garanta que campos sensíveis nunca vazam (passwords, hashes, private tokens, internal secrets).

---

# Frontend Testing (Vitest)

> Aplica-se **quando o user pede** testes de componentes React, hooks, stores ou utils de frontend.

## Stack canônica

- **Vitest 4 + @testing-library/react + jsdom + bun.** Sem jest-dom/user-event/msw por default.
- Config no bloco `test:` do `vite.config.ts` (`defineConfig` importado de `vitest/config`):
  `environment: "jsdom"` · `globals: true` · `setupFiles: ["./src/test/setup.ts"]` (cleanup do
  testing-library) · `css: false`. Plugin tanstackRouter com `routeFileIgnorePattern: "__tests__"`.
- Script `"test": "vitest run"`; entra no `check.sh` como step antes do build.
- Imports explícitos de `"vitest"` (`describe, it, expect, vi`) mesmo com `globals: true`.

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
- Mock de API no nível do hook (`vi.mock("@/hooks/useX", ...)`) + `vi.clearAllMocks()` no
  `beforeEach`. Sem msw.
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
  quantas chamadas o bootstrap gasta); os specs são idênticos nos 5. Rota home = tela de lista que
  aguenta `PagedResponse` vazio — dashboard que depende de payload de KPI quebra no mock.
- Script `"test:e2e": "playwright test"` — **fora do `check.sh` padrão** (sobe dev server + 2
  browsers); entra em alvo próprio (`bash check.sh --e2e`) para não tornar o check local lento.
