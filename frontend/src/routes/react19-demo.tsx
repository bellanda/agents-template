import { HeartIcon, SpinnerIcon } from "@phosphor-icons/react";
import { createFileRoute } from "@tanstack/react-router";
import { Suspense, use, useActionState, useOptimistic, useState, useTransition } from "react";
import { z } from "zod";

import { SidebarLayout } from "@/components/layouts";
import { Button } from "@/components/ui/button";

// =============================================================================
// React 19 Primitives — Seed Patterns
// =============================================================================
// Este arquivo mostra os 3 primitives canônicos que substituem `useEffect + useState`
// na maior parte dos casos. Skill `react-19-patterns` tem a tabela de decisão completa.
// =============================================================================

export const Route = createFileRoute("/react19-demo")({
  component: React19DemoPage,
});

function React19DemoPage() {
  return (
    <SidebarLayout>
      <div className="mx-auto flex max-w-3xl flex-col gap-12 p-8">
        <header className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold">React 19 — Seed Patterns</h1>
          <p className="text-muted-foreground">useActionState · useOptimistic · use() + Suspense</p>
        </header>

        <CommentFormSeed />
        <LikeButtonSeed />
        <UserProfileSeed />
      </div>
    </SidebarLayout>
  );
}

// =============================================================================
// 1. Form com submit async  →  useActionState + Form Action
// =============================================================================

const commentSchema = z.object({
  comment: z.string().min(3, "Mínimo 3 caracteres").max(200, "Máximo 200"),
});

type CommentActionState = { success: boolean; error: string | null };

async function submitCommentAction(
  _prev: CommentActionState,
  formData: FormData
): Promise<CommentActionState> {
  const parsed = commentSchema.safeParse({ comment: formData.get("comment") });
  if (!parsed.success) {
    return {
      success: false,
      error: parsed.error.issues[0]?.message ?? "Inválido",
    };
  }
  // Simula network — substitua por fetch real.
  await new Promise((r) => setTimeout(r, 800));
  if (Math.random() < 0.3) return { success: false, error: "Falha no servidor (mock)" };
  return { success: true, error: null };
}

function CommentFormSeed() {
  const [state, action, isPending] = useActionState(submitCommentAction, {
    success: false,
    error: null,
  });

  return (
    <section className="bg-card flex flex-col gap-3 rounded-lg border p-6">
      <h2 className="font-semibold">1. Form async com `useActionState`</h2>
      <p className="text-muted-foreground text-sm">
        1 hook substitui `useState(loading) + useState(error) + handleSubmit + try/finally`.
      </p>
      <form action={action} className="flex flex-col gap-3">
        <textarea
          name="comment"
          className="bg-background rounded-md border p-2 text-sm"
          rows={3}
          placeholder="Deixe um comentário..."
        />
        <Button type="submit" disabled={isPending} className="self-start">
          {isPending && <SpinnerIcon className="size-4 animate-spin" />}
          {isPending ? "Enviando..." : "Enviar"}
        </Button>
        {state.error && <p className="text-destructive text-sm">{state.error}</p>}
        {state.success && <p className="text-sm text-emerald-600">Comentário enviado.</p>}
      </form>
    </section>
  );
}

// =============================================================================
// 2. Optimistic UI  →  useOptimistic + rollback automático
// =============================================================================

function LikeButtonSeed() {
  const [serverLikes, setServerLikes] = useState(42);
  const [optimisticLikes, addOptimisticLike] = useOptimistic(
    serverLikes,
    (current, delta: number) => current + delta
  );
  const [isPending, startTransition] = useTransition();

  function handleLike() {
    startTransition(async () => {
      addOptimisticLike(1); // UI atualiza imediato
      await new Promise((r) => setTimeout(r, 600)); // mock network
      // Em produção: await mutation.mutateAsync() e deixe TanStack Query invalidar.
      // Se rejeitar, useOptimistic rebobina pro serverLikes automaticamente.
      setServerLikes((prev) => prev + 1);
    });
  }

  return (
    <section className="bg-card flex flex-col gap-3 rounded-lg border p-6">
      <h2 className="font-semibold">2. Optimistic UI com `useOptimistic`</h2>
      <p className="text-muted-foreground text-sm">
        Se a request rejeitasse, React rebobinaria pro valor real automaticamente — sem try/catch +
        setState manual.
      </p>
      <Button onClick={handleLike} disabled={isPending} className="gap-2 self-start">
        <HeartIcon className="size-4" weight={optimisticLikes > serverLikes ? "fill" : "regular"} />
        {optimisticLikes} likes
      </Button>
    </section>
  );
}

// =============================================================================
// 3. Data fetching com Promise prop  →  use() + Suspense
// =============================================================================

function fetchRandomUser(): Promise<{ name: string; bio: string }> {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        name: "Ada Lovelace",
        bio: "Mathematician — wrote the first algorithm.",
      });
    }, 700);
  });
}

// Promise estável fora do componente — em prod, viria de route loader / useMemo / TanStack Query.
const userPromise = fetchRandomUser();

function UserProfileSeed() {
  return (
    <section className="bg-card flex flex-col gap-3 rounded-lg border p-6">
      <h2 className="font-semibold">3. Data fetching com `use(promise)` + Suspense</h2>
      <p className="text-muted-foreground text-sm">
        Pattern para fluxo server-driven (route loader passa Promise). Em SPA puro,{" "}
        <strong>TanStack Query continua sendo o default</strong> — use() entra quando faz sentido
        suspender a árvore.
      </p>
      <Suspense fallback={<div className="text-muted-foreground text-sm">Carregando...</div>}>
        <UserCard userPromise={userPromise} />
      </Suspense>
    </section>
  );
}

function UserCard({ userPromise }: { userPromise: Promise<{ name: string; bio: string }> }) {
  const user = use(userPromise);
  return (
    <div className="bg-muted/40 rounded-md p-4">
      <p className="font-medium">{user.name}</p>
      <p className="text-muted-foreground text-sm">{user.bio}</p>
    </div>
  );
}
