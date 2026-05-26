# Data Fetching — `use(promise)` + Suspense

## Quando usar

Quando o componente recebe **uma Promise como prop** vinda de um loader/route/parent que orquestra o fetch. Em SPA Vite com TanStack Query, isso geralmente significa: route `loader` retorna Promise, route component recebe e passa pra filho que faz `use()`.

**Default do projeto continua sendo TanStack Query.** `use()` entra quando faz sentido suspender a árvore (ex: detail page que precisa de N dados pra renderizar QUALQUER coisa) ou quando o loader já fetched antes do componente montar.

## Pattern canônico

```tsx
// route loader (TanStack Router)
export const Route = createFileRoute("/users/$userId")({
  loader: ({ params }) => ({
    userPromise: fetchUser(params.userId), // NÃO await — passa a promise
  }),
  component: UserPage,
});

function UserPage() {
  const { userPromise } = Route.useLoaderData();
  return (
    <ErrorBoundary fallback={<UserError />}>
      <Suspense fallback={<UserSkeleton />}>
        <UserProfile userPromise={userPromise} />
      </Suspense>
    </ErrorBoundary>
  );
}

function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  const user = use(userPromise); // suspende até resolver
  return <UserCard user={user} />;
}
```

## Anti-pattern que isso substitui

```tsx
// ❌ ANTES — useEffect + 3 estados + cancel flag
function UserProfile({ userId }: { userId: string }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchUser(userId)
      .then((data) => !cancelled && setUser(data))
      .catch((err) => !cancelled && setError(err))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (loading) return <Spinner />;
  if (error) return <ErrorBoundary />;
  return <UserCard user={user!} />;
}
```

3 estados, cancel flag, ordem de set, casos NULL — tudo isso desaparece com `use()` + Suspense.

## Regras

- `use()` pode ser chamado **condicionalmente** e dentro de loops — única exceção às Rules of Hooks.
- Sempre envolver em `<Suspense fallback={...}>` (loading) **e** `<ErrorBoundary fallback={...}>` (error). Sem um dos dois, app crasha.
- A Promise tem que ser **estável** entre renders (criada no loader, em `useMemo`, ou em parent estável). Promise nova a cada render = re-suspend infinito.
- Em TanStack Router, `loader` é o lugar natural — ele só roda quando a rota entra/muda.

## Quando NÃO usar

- Lista paginada / filtros dinâmicos / refetch on focus → **TanStack Query** com `useQuery`. `use()` não tem cache, dedup, retry, stale.
- Mutação (POST/PATCH/DELETE) → `useActionState` ou TanStack `useMutation`.
- Component fetcha pro próprio uso (não recebe Promise) → TanStack Query.

`use()` é Suspense-native. Use quando o ponto da feature é **suspender a árvore até os dados chegarem**.
