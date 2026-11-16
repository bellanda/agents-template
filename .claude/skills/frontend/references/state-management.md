# Frontend State Management — Onde Mora Cada Coisa

> Reference do gate `frontend` (item 4 do checklist). Onde mora cada pedaço de state.

5 níveis de state, cada um com tooling específico. Confundir → bug clássico (state que não sobrevive refresh, re-render storm, dois sources of truth divergindo).

## Tabela de decisão

| Level         | Tool                          | When                                            | Sobrevive refresh? |
| ------------- | ----------------------------- | ----------------------------------------------- | ------------------ |
| Local         | `useState`                    | Modals, toggles, hover — single component       | ❌                 |
| URL           | `useSearch` (TanStack Router) | Filters, pagination, search query, tab ativa    | ✅                 |
| Server        | TanStack Query                | TODA API data — listas, detalhes, mutations     | ✅ (cache via key) |
| Deep UI       | React Context                 | UI state 3+ níveis deep (theme, modal manager)  | ❌                 |
| Outside React | Zustand                       | Auth tokens, org ID, qualquer leitura fora hook | Configurável       |

## 1. Local — `useState`

Use para state que vive em **1 component só** e não precisa sobreviver a unmount/refresh.

```tsx
function EditButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Editar</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        ...
      </Dialog>
    </>
  );
}
```

Casos: modal `open`, dropdown `expanded`, hover state, input não-controlado, accordion `activeIndex`.

NUNCA: dados de API, filtros que afetam URL, auth state, dados que múltiplos components precisam.

## 2. URL — `useSearch` (TanStack Router)

Filtros, pagination, busca, tab ativa — qualquer coisa que define **o que o usuário está olhando** vai pra URL. Sobrevive refresh, é shareable, voltar/avançar funciona.

```tsx
import { z } from "zod";
import { createFileRoute } from "@tanstack/react-router";

const searchSchema = z.object({
  q: z.string().optional(),
  status: z.enum(["open", "closed", "all"]).default("all"),
  page: z.number().int().min(1).default(1),
});

export const Route = createFileRoute("/conversations")({
  validateSearch: searchSchema,
  component: ConversationsPage,
});

function ConversationsPage() {
  const { q, status, page } = Route.useSearch();
  const navigate = Route.useNavigate();

  return (
    <div>
      <Input
        value={q ?? ""}
        onChange={(e) =>
          navigate({
            search: (prev) => ({ ...prev, q: e.target.value, page: 1 }),
          })
        }
      />
      <Select
        value={status}
        onValueChange={(v) =>
          navigate({
            search: (prev) => ({ ...prev, status: v as any, page: 1 }),
          })
        }
      />
      <ConversationList q={q} status={status} page={page} />
    </div>
  );
}
```

Critical:

- `validateSearch` com Zod 4 — type-safe + runtime check.
- Reset `page: 1` ao mudar filtro (evita 404 "page 5 of 0").
- `navigate({ search: (prev) => ... })` para updates parciais.

Casos: search query, filter pills, pagination, tab ativa, ID selecionado de detail panel.

NUNCA: state que muda 60fps (slider arrastando — use local + debounce pra URL).

## 3. Server — TanStack Query

TODA data de API vive em TanStack Query. Cache, dedup, retry, stale-while-revalidate, optimistic updates — tudo resolvido. Duplicar em Context/store é o anti-padrão #1.

```tsx
import { useQuery } from "@tanstack/react-query";
import { client } from "@/lib/api/client";

export function useConversations(q: string, status: string, page: number) {
  return useQuery({
    queryKey: ["conversations", { q, status, page }],
    queryFn: async () => {
      const res = await client.get<PagedResponse<Conversation>>(
        `/conversations?q=${q}&status=${status}&page=${page}`,
      );
      return res.data;
    },
    staleTime: 30_000,
  });
}
```

Mutations:

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function useUpdateConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; status: string }) =>
      client.patch(`/conversations/${input.id}`, { status: input.status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
```

Critical:

- `queryKey` inclui TODOS os params variáveis (search, page, filters) — cache key bate exato.
- Invalidate por prefix: `["conversations"]` invalida todas variantes.

### Frescor, invalidação e rascunho — política da frota (decisão do usuário 2026-11-13)

Auditoria 2026-11-13: "preciso dar F5" vinha de `staleTime` 5 min + foco desligado + mutation sem
invalidação. Canônico no template: `lib/api/query-client.ts` (`createAppQueryClient`,
`DEFAULT_STALE_TIME_MS`), `lib/api/invalidation.ts`, `lib/api/entity-dependencies.ts`,
`hooks/useSyncedDraft.ts`.

- **Default = dado fresco**: `staleTime` 30 s, `refetchOnWindowFocus` + `refetchOnReconnect` ligados
  (só query ATIVA e velha refaz, custo baixo), **mutation NUNCA é repetida sozinha** (retry de POST
  duplica efeito). Não suba o default global.
- **Cache longo é escolha consciente** (catálogo estático, vocabulário, permissões): `staleTime`
  explícito NA query + comentário com o porquê. Sem comentário = bug.
- **Toda mutation de escrita atualiza o cache**: `onSuccess: () => invalidateEntity(queryClient,
  orgId, "<entidade>")` (ou `invalidateEntityDependents` quando a tela já faz cirurgia de cache, ou
  `setQueryData`). A tabela `entity-dependencies.ts` (uma por app) diz quem depende de quem; a
  mutation nunca escolhe chaves à mão (concluir/avançar negociação ou avaliação = `invalidateEntity`
  com a entidade). `useCrud` já chama `invalidateEndpointDependents` e invalida as queries irmãs
  do mesmo endpoint (pending, locations, overdue-count). Exceção (download/export, sem efeito em
  dado) leva comentário dizendo por que não invalida. Verificação: `rg -n "useMutation\(" src` →
  cada ocorrência tem `onSuccess` com invalidate/`setQueryData` ou o comentário.
- **Chave frouxa invalida nada**: hook com chave `["repairs", orgId]` fora do vocabulário da
  entidade passa batido em `invalidateEntity`; ponha a chave no `keys` da entidade, ou re-chaveie o
  hook para a cabeça da chave pertencer à entidade que deve ser invalidada (nexarena tinha
  `["organizations","finance",…]`). Chaves de publicação de portal (`vehiclePublications`,
  `storePublishOptions`) fora do caminho de `vehicle` exigem entidade `publication` dependente de
  `vehicle` e de `portal`.
- **Formulário que parte de query usa `useSyncedDraft`** (`server`, `toDraft`, `draft`, `setDraft`,
  `entityKey`; `markSaved()` depois de salvar). PROIBIDO `useEffect(() => setForm(query.data), [query.data])`:
  o refetch de foco apaga o que a pessoa digita. Rascunho sujo nunca é sobrescrito.
- **Rascunho em `localStorage`**: chave por usuário+org num módulo único de chaves, purgada no logout.
- **Dashboard que promete tempo real**: assina `entity.changed/dashboard` (ver
  `realtime-and-push-actions.md`) e mantém `refetchInterval` de segurança de 60 s.
- **Tela operacional sem canal ao vivo**: `useCollectionList`/`useInfiniteList`/`usePagedList`
  aceitam `poll` opt-in (`ListPoll`: itens → intervalo em ms, ou `false`), só em primeiro plano.
  Origem: akmeo (`hooks/useCollectionList.ts`); ainda não propagado ao template/frota.

NUNCA:

- Copiar `data` da query pra `useState`/Zustand. Single source of truth = cache do TanStack Query.
- `useEffect + setState` pra "salvar" data. Use `select:` no `useQuery` se precisa derivar.

## 4. Deep UI — React Context

State puramente de UI que precisa atravessar 3+ níveis. Theme, modal manager global, sidebar collapsed state.

```tsx
import { createContext, useContext, useMemo, useState } from "react";

type SidebarContextValue = {
  collapsed: boolean;
  toggle: () => void;
};

const SidebarContext = createContext<SidebarContextValue | null>(null);

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const value = useMemo(
    () => ({ collapsed, toggle: () => setCollapsed((c) => !c) }),
    [collapsed],
  );
  // React 19: <Context value={...}> direto, sem .Provider
  return <SidebarContext value={value}>{children}</SidebarContext>;
}

export function useSidebar() {
  const ctx = useContext(SidebarContext);
  if (!ctx) throw new Error("useSidebar must be inside <SidebarProvider>");
  return ctx;
}
```

Critical:

- **SEMPRE `useMemo`** no `value` com deps primitivas. Sem isso, todo re-render do provider re-renderiza TODOS os consumers (re-render storm).
- React 19: `<MyContext value={...}>` (sem `.Provider`).

NUNCA:

- Context com `value={{ a, b, c }}` inline sem `useMemo`.
- Context pra data de API (use TanStack Query).
- Context pra auth token (use Zustand — precisa ser lido fora de hooks, em ApiClient).

## 5. Outside React — Zustand

Tudo que precisa ser **lido de código fora de hooks** — ApiClient, route loaders, interceptors, axios/fetch wrappers. Zustand expõe `store.getState()` síncrono.

```tsx
import { create } from "zustand";

type AuthState = {
  user: { id: string; name: string; email: string; roles: string[] } | null;
  setUser: (user: AuthState["user"]) => void;
  reset: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  reset: () => set({ user: null }),
}));

// Hook usage
function Header() {
  const user = useAuthStore((s) => s.user);
  return <span>{user?.name}</span>;
}

// Fora do React (em ApiClient)
function getCurrentUserId() {
  return useAuthStore.getState().user?.id;
}
```

Outro caso típico: `organizationStore` lido em `beforeLoad` de TanStack Router (que roda fora do React).

Critical:

- Selector function (`(s) => s.user`) ao usar como hook — só re-renderiza se o slice mudar.
- `useAuthStore.getState()` fora de React.
- **SEM `persist`** em auth store — access token vai pra memória + cookie HttpOnly. Persist em localStorage = vulnerability.

Quando OK usar `persist` (não-auth): preferences de UI (theme, sidebar collapsed default), drafts de form long-form. Sempre justifique.

## Anti-padrões clássicos

### ❌ Duplicar API data em store

```tsx
// BAD
const { data: conversations } = useQuery(...);
useEffect(() => {
  useConversationStore.getState().setAll(conversations);
}, [conversations]);
```

Por que: dois sources of truth. Mutation invalida o cache mas não atualiza o store, ou vice-versa. Bug garantido.

Faça: use o cache do TanStack Query direto. Se precisa derivar, `select:`. Se precisa cross-component, mesma `queryKey` — cache é compartilhado.

### ❌ State em React quando devia ser URL

```tsx
// BAD
const [tab, setTab] = useState<"open" | "closed">("open");
```

Por que: refresh perde a tab. Link compartilhado abre na tab default. Voltar do browser não funciona.

Faça: `useSearch` com Zod schema.

### ❌ Context sem `useMemo` no value

```tsx
// BAD
<MyContext value={{ user, settings, toggle }}>
```

Por que: novo objeto a cada render → todos os consumers re-renderizam mesmo sem mudança real.

Faça: `useMemo(() => ({ user, settings, toggle }), [user, settings])` com deps primitivas.

### ❌ Auth token em Zustand `persist`

```tsx
// BAD
export const useAuthStore = create(persist((set) => ({ accessToken: null, ... }), { name: "auth" }));
```

Por que: localStorage é acessível por JS de qualquer XSS. Cross-tab sync sem coordenação quebra refresh.

Faça: access token em memória (`lib/api/access-token-store.ts`), refresh token em cookie HttpOnly path-scopado. Cross-tab via BroadcastChannel + Web Locks API. Ver gate `auth`.

## Don'ts

- **NUNCA** duplique API data em Zustand/Context — TanStack Query é o cache.
- **NUNCA** Context com `value={{...}}` inline sem `useMemo`.
- **NUNCA** `persist` em auth/token store.
- **NUNCA** filtros/pagination em `useState` — URL é onde isso vive.
- **NUNCA** `useEffect + setState` pra "salvar" valor de query.
- **NUNCA** Zustand selector que retorna objeto novo (`(s) => ({ a, b })`) — sempre primitive ou shallow-stable.
- **NUNCA** crie store global pra state que vive em 1 component só.
