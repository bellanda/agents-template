# Forms — `useActionState` + Form Actions + `useFormStatus`

## Pattern canônico

```tsx
import { useActionState } from "react";

type ActionResult = { success: boolean; error: string | null };

async function submitComment(
  _prev: ActionResult,
  formData: FormData,
): Promise<ActionResult> {
  const text = formData.get("comment") as string;
  try {
    await postComment(text);
    return { success: true, error: null };
  } catch (e) {
    return { success: false, error: (e as Error).message };
  }
}

export function CommentForm() {
  const [state, action, isPending] = useActionState(submitComment, {
    success: false,
    error: null,
  });

  return (
    <form action={action}>
      <textarea name="comment" required />
      <SubmitButton />
      {state.error && <p className="text-destructive">{state.error}</p>}
      {state.success && <p className="text-success">Comentário enviado.</p>}
    </form>
  );
}

function SubmitButton() {
  const { pending } = useFormStatus(); // lê do form ancestral
  return (
    <Button disabled={pending}>
      {pending ? <Spinner data-icon="inline-start" /> : null}
      {pending ? "Enviando..." : "Enviar"}
    </Button>
  );
}
```

## Por que isso é o novo default

- 1 hook (`useActionState`) substitui `useState(loading) + useState(error) + useState(success) + handleSubmit + tryFinally`.
- `<form action={fn}>` repassa `FormData` direto — sem `e.preventDefault()`, sem `new FormData(e.target)`.
- `useFormStatus()` lido no filho não exige prop drilling do `isPending` nem context.
- Estado acumulado: `state` na próxima invocação é o retorno da anterior — perfect pra "lista de erros", "tentativas restantes", etc.

## Anti-pattern que isso substitui

```tsx
// ❌ ANTES
function CommentForm() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);
    try {
      await postComment(text);
      setSuccess(true);
      setText("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  /* ... */
}
```

4 useState + handler de 15 linhas → 1 useActionState + 5 linhas de action function.

## Integração com TanStack Form + Zod

TanStack Form continua sendo o default para forms com **validação cliente complexa, multi-step, field-level errors em tempo real**. Para forms simples (1-3 fields, submit-only validation), `useActionState` ganha em verbosidade.

Híbrido válido: TanStack Form para validação + estado dos campos, `useActionState` para o submit async. O `action` do `<form>` recebe a função do `useActionState`; TanStack Form gerencia os campos.

## Regras

- Action function sempre tem assinatura `(prevState, formData) => Promise<state>` ou `(prevState, formData) => state`.
- O retorno é o **próximo `state`** — não set state manualmente.
- `useFormStatus` SÓ funciona dentro de um `<form>` que tem `action` (React 19 form). Em `<form onSubmit>` legado não funciona.
- `<form action={fn}>` reseta o form automaticamente em submit bem-sucedido. Para preservar campos em erro, retornar os valores no `state`.

## Quando NÃO usar

- Form sem submit (apenas filtros que atualizam URL via `useSearch`) → `useSearch` do TanStack Router.
- Mutação que NÃO é form (botão "Delete", toggle) → TanStack `useMutation` ou `useOptimistic`.
- Multi-step wizard com state complexo entre steps → state machine (Zustand, XState) + `useActionState` por step.
