# Optimistic UI — `useOptimistic`

## Pattern canônico

```tsx
import { useOptimistic, useTransition } from "react";

export function LikeButton({ post }: { post: Post }) {
  const [optimisticLikes, addOptimisticLike] = useOptimistic(
    post.likes,
    (current, delta: number) => current + delta,
  );
  const [, startTransition] = useTransition();

  function handleLike() {
    startTransition(async () => {
      addOptimisticLike(1); // UI atualiza instantaneamente
      await likePost(post.id); // se rejeitar, React rebobina pro estado real
    });
  }

  return (
    <Button onClick={handleLike}>
      <HeartIcon data-icon="inline-start" />
      {optimisticLikes}
    </Button>
  );
}
```

## A mágica

Se `likePost(post.id)` rejeitar, **React reseta automaticamente** `optimisticLikes` para `post.likes`. Sem `try/catch` manual, sem `setState(rollback)`, sem flag de "is rolling back".

Quando a request resolve com sucesso, `post.likes` (do server / TanStack Query / props) eventualmente atualiza, e `useOptimistic` re-sincroniza com o novo valor real.

## Anti-pattern que isso substitui

```tsx
// ❌ ANTES — rollback manual frequentemente errado
function LikeButton({ post }: { post: Post }) {
  const [count, setCount] = useState(post.likes);
  const [pending, setPending] = useState(false);

  async function handleLike() {
    const prev = count;
    setCount(count + 1);
    setPending(true);
    try {
      await likePost(post.id);
    } catch {
      setCount(prev); // rollback manual
    } finally {
      setPending(false);
    }
  }
  /* + sync com prop quando post.likes muda em outro tab... */
}
```

O bug clássico: prop `post.likes` muda (outra ação atualizou) mas `count` local está congelado. `useOptimistic` resolve isso lendo a base do server a cada render.

## Casos canônicos

- Like / unlike, upvote / downvote, star.
- Mark as read / unread.
- Drag-reorder (passar lista reordenada antes do server confirmar).
- Add item a uma lista (carrinho, todo list).
- Remove item (mostrar desaparecimento imediato).

## Regras

- `useOptimistic` SEMPRE roda dentro de um `startTransition` ou Action — fora disso, o React não consegue rastrear o rollback.
- O primeiro argumento é a **fonte da verdade** (do server / props / query) — `useOptimistic` re-sincroniza com ele.
- O reducer (segundo argumento) é puro: `(current, action) => nextState`. Sem side effects.
- Para listas, o "action" pode ser o item inteiro + tipo: `(items, action) => action.type === "add" ? [...items, action.item] : items.filter(...)`.

## Integração com TanStack Query

```tsx
const { data: post } = useQuery({ queryKey: ["post", id], queryFn: ... });
const mutation = useMutation({ mutationFn: likePost });

const [optimisticLikes, addOptimisticLike] = useOptimistic(
  post?.likes ?? 0,
  (current, delta: number) => current + delta,
);

function handleLike() {
  startTransition(async () => {
    addOptimisticLike(1);
    await mutation.mutateAsync(post!.id);
    // TanStack Query invalida e refetch → post.likes atualiza
  });
}
```

Para invalidação automática, usar `onSuccess: () => queryClient.invalidateQueries(...)` na mutation. `useOptimistic` cuida da janela entre "click" e "server confirma".

## Quando NÃO usar

- Mutação que não tem feedback visual imediato (background sync) → `useMutation` puro.
- Operações que precisam de confirmação user-side primeiro (delete com modal) — confirme antes, aplica optimistic depois.
- Server retorna dados que o client não consegue prever (ex: ID gerado, timestamp) — usar `useOptimistic` só pra parte previsível, deixar o resto pro server.
