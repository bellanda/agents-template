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

## Toasts — sonner

- `import { toast } from "sonner"`; um `<Toaster/>` na raiz (com `offset` p/ safe-area — ver
  `mobile-keyboard.md`). `toast.success` ao salvar, `toast.error(err.message)` no `onError` da
  mutation, `toast.promise` para operação longa (upload, geração).
- Texto pt-BR curto, no pretérito ("Equipe atualizada"); erro mostra a mensagem do `ApiError`/
  `UploadError`, nunca o objeto cru.
- Erro de **validação de campo** vai no campo; toast é para o resultado da ação.
- Proibido `alert()`, e `<p className="text-destructive">` como único retorno de uma mutation.

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
