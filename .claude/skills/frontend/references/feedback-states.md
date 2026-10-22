# Estados de feedback — vazio, erro, offline, confirmação, toast, skeleton

> Reference do gate `frontend`. Abra ANTES de desenhar qualquer estado que não é o "caminho feliz"
> de uma tela: sem dados, falha de carga, sem rede, confirmar destrutivo, resultado de ação,
> carregando. Padronizado em **2026-10-01** com o **kailos** como canônico (`EmptyState`, aviso
> offline); `ConfirmDialog` é o de sempre (`confirm-dialog.tsx` + `overlays.md`).

**Princípio:** cada situação tem UM componente e UMA hierarquia de texto em todos os apps. Coleção
vazia, coleção que falhou ao carregar, rede fora e carregando são **quatro fatos diferentes** — nunca
a mesma tela.

## Tabela de decisão

| Situação                                              | Use                                                                  |
| ----------------------------------------------------- | -------------------------------------------------------------------- |
| "Ainda não há nada aqui" (lista, aba, card, seção)    | **`EmptyState`** (`ui/empty-state.tsx`)                              |
| Coleção FILTRADA sem resultado                        | `DataList` + `onClearFilters` ("Limpar filtros") — mesmo `EmptyState` |
| A query falhou (rede, 500, 403)                       | `ErrorState` do `DataList` / bloco de erro com "Tentar novamente" — **nunca** `EmptyState` |
| Rota quebrou / exceção de render                      | `RouteErrorFallback` (`components/error-fallback.tsx`)                |
| Aparelho sem rede                                     | `NetworkStatusBanner` no shell (faixa, não toast)                     |
| Confirmar ação destrutiva/irreversível                | **`ConfirmDialog`** — único                                           |
| Resultado de uma ação (salvou, falhou, enviado)       | **toast** sonner                                                      |
| Primeira carga de layout conhecido (cards, form, tabela) | **`Skeleton`** com a forma do conteúdo                             |
| Ação em andamento num botão                           | spinner inline no botão (`busy`/`disabled`)                           |

## `EmptyState` — `ui/empty-state.tsx` (standalone)

```tsx
<EmptyState
  icon={LuUsers}                                  // react-icons, decorativo (aria-hidden)
  title="Nenhuma equipe criada ainda"
  description="Crie a primeira para a IA ter para quem transferir."
  action={<Button onClick={openCreate}>Nova equipe</Button>}
  size="compact"                                  // "default" (py-16, página/lista) | "compact" (py-8, dentro de Card/seção)
/>
```

- Hierarquia fixa: ícone opcional em círculo `bg-muted` → `title` (`text-sm font-medium`) →
  `description` (`text-muted-foreground text-xs`) → CTA. Texto pt-BR; título diz o fato
  ("Nenhum veículo cadastrado"), descrição diz o próximo passo, CTA executa.
- É **o mesmo** bloco que o `DataList` usa internamente — não existe mais `EmptyState` privado dentro
  de componente. Tela sem `DataList` (aba, card, seção de settings) usa o avulso.
- Texto solto `<p className="text-muted-foreground py-8 text-center">Nenhum…</p>` e "Carregando…"
  em texto puro são o antipadrão que ele substitui.
- **Não** serve para erro de carga nem para loading.

## Erro de carga ≠ vazio

Query que falha sem tratamento cai em `items = []` e a tela diz "Nenhum veículo encontrado" — o
usuário conclui que o estoque está vazio. `DataList`/`StaticDataList` aceitam `isError/error/refetch`
(spread do hook de lista) e renderizam o `ErrorState` ("Não foi possível carregar esta lista" +
mensagem normalizada + "Tentar novamente"). Fora de lista, mesmo desenho: ícone `LuTriangleAlert` em
`text-destructive`, `role="alert"`, botão de retry. Falha de rede tem **uma** mensagem pt-BR
(`lib/api/network-error.ts`, `isNetworkFailure` — ver `api-and-csp.md`); nunca o texto cru do
browser ("Load failed").

## Aviso "sem conexão" — `NetworkStatusBanner` + `useOnlineStatus`

```ts
// hooks/useOnlineStatus.ts
useSyncExternalStore(subscribe /* window online|offline */, () => navigator.onLine, () => true);
```

- Faixa âmbar (`role="status"`, `aria-live="polite"`, "Sem conexão — tentando reconectar…") montada
  **UMA vez** no shell autenticado, logo abaixo do header (junto do `OrgBlockedBanner`). Some sozinha
  quando a rede volta; **sem botão** (não há o que o usuário fazer).
- É **feedback, não sessão**: só LÊ `navigator.onLine`; nunca toca em auth/token/redirect (rede que cai
  não desloga — ver regra de auth "só 401/403 encerram"). O TanStack Query já pausa/retoma queries
  offline. `navigator.onLine === true` pode mentir (Wi-Fi sem internet) → a falha pontual segue pelo
  erro da própria request.
- `useOnlineStatus()` também serve para desabilitar ação que exige rede. É estado persistente, por
  isso é faixa e não toast.

## Confirmação — `ConfirmDialog` é o ÚNICO

- Toda confirmação destrutiva/irreversível usa `ui/confirm-dialog.tsx` (`destructive`, `busy`,
  `pendingLabel`; o pai fecha no `onSuccess`). Em lista, um único `ConfirmDialog` no container.
- **`AlertDialog` cru PROIBIDO fora de `components/ui/`** (decisão 2026-10-01; `ui/alert-dialog.tsx` e
  `ui/confirm-dialog.tsx` são os únicos que o importam). Achou `AlertDialog*` em componente de tela →
  trocar por `ConfirmDialog`. Se a necessidade não é confirmar (aviso bloqueante com uma saída), é
  `Dialog`/`FormDialog`, não `AlertDialog`.
- Tira inline, accordion, button-swap, `window.confirm`: proibidos (ver `overlays.md`).

## Toasts — sonner (padrão da frota, decisão do usuário 2026-10-22)

Canônico: kailos `lib/api/notify.ts` + `lib/api/query-client.ts` + `components/ui/sonner.tsx`.

**Formato único de erro**: título com a AÇÃO que falhou + descrição com o MOTIVO do backend.

```ts
// ✅ título "Não foi possível <verbo> <objeto concreto>" + motivo via errorMessage()
notifyError("Não foi possível iniciar a autorização", err);
// ❌ genérico, sem motivo, ou o motivo no título
toast.error("Erro ao salvar");
toast.error(errorMessage(err));
toast.error(`Erro: ${err.message}`);
```

- **Um caminho só para erro na tela: `notifyError(title, error)`** (`lib/api/notify.ts`). Ele mostra
  `toast.error(title, { description: errorMessage(error) })`, cala 401 (fluxo de sessão), acrescenta
  `(código xxxxxxxx)` do `request_id` em 5xx e manda o erro para o log do backend (`rules/logs.md`
  → "Logs do frontend"). `error` pode ser uma frase pronta para validação local sem erro de API.
- **Mutation declara o título em `meta.errorTitle`** no `useMutation`; o handler global da
  `MutationCache` mostra o toast. A tela NÃO mostra toast no `catch`/`onError` — fica só a lógica
  de UI (fechar dialog, reverter otimista). Quer um título com dado da tela (nome do portal)?
  `notifyError(título, err)` no `catch`: o id de toast é POR OBJETO DE ERRO, então o toast do
  global é SUBSTITUÍDO, nunca duplicado. Bug que originou isso: o global rodava antes do `catch` e
  saíam dois toasts (kailos, Portais → "Autorizar", 2026-10-22). O guard antigo
  `if (mutation.options.onError) return` não enxerga `mutate(v, { onError })` nem `mutateAsync` +
  `catch` — não use.
- Query: o global usa `meta.errorTitle ?? "Não foi possível carregar os dados"` com id
  `query-error:<hash>` (polling que falha = um toast). `meta.silentError` = a tela mostra o erro
  inline (`ErrorState`, erro de login no form) ou ele é esperado. `meta` é tipado via `Register`.
- **Cores**: `<Sonner richColors>` no `components/ui/sonner.tsx` — erro vermelho, sucesso verde,
  aviso amarelo, info azul, com variante escura pelo `theme`. O toast neutro fica nas `--normal-*`
  (popover). Tom por app (tokens `--success-*`/`--error-*`/`--warning-*`/`--info-*` no `style` do
  Toaster) é identidade, não padrão.
- `notifySuccess(title, description?)` / `toast.success` ao concluir; `notifyWarning` para resultado
  parcial (amarelo, também vai para o log como `warning`); `toast.promise` para operação longa.
- Texto pt-BR curto. Sucesso no pretérito ("Equipe atualizada"). Título de erro SEMPRE
  "Não foi possível …" com objeto concreto ("o veículo", "a meta de vendas") — nunca "Erro ao …",
  "Algo deu errado", "Ocorreu um erro".
- Erro de **validação de campo** vai no campo; toast é para o resultado da ação.
- Proibido `alert()`, e `<p className="text-destructive">` como único retorno de uma mutation.
- Auditoria: `rg -n "toast\.error\(" frontend/src` — só sobram validações locais com
  `{ description }`; todo erro de API passa por `notifyError`/`meta.errorTitle`.

## Skeletons e loading

- Primeira carga de uma região de forma conhecida → `Skeleton` (`ui/skeleton.tsx`) com a geometria do
  conteúdo (linhas de card, bolhas, campos), nunca "Carregando…" em texto nem spinner de página.
- Refetch com dado em tela → mantém o dado (`placeholderData: keepPreviousData`), `DataList`
  escurece as linhas; não volta ao skeleton.
- Spinner só dentro de botão/ação inline.

## Anti-padrões

- **NUNCA** `EmptyState`/"Nenhum X" para query que falhou.
- **NUNCA** `EmptyState` privado dentro de componente de lista — um só, `ui/empty-state.tsx`.
- **NUNCA** `AlertDialog` cru em tela; **NUNCA** `window.confirm`/`alert`.
- **NUNCA** deslogar nem redirecionar por evento `offline`.
- **NUNCA** toast para estado persistente (offline) nem faixa para resultado pontual de ação.
- **NUNCA** texto de erro cru do browser/`Error.message` técnico na tela.
- **NUNCA** `toast.error` no `catch`/`onError` de mutation — `meta.errorTitle` ou `notifyError`.
- **NUNCA** título genérico ("Erro ao salvar", "Algo deu errado") nem o motivo no lugar do título.
