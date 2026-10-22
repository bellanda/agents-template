import { createRouter, type ErrorComponentProps } from "@tanstack/react-router";
import { useEffect } from "react";

import { reportClientError } from "@/lib/observability/client-logger";

// Import the generated route tree
import { routeTree } from "./routeTree.gen";

// Tela quebrada é o erro que o usuário mais vê e o backend menos sabe: vai para o log.
function RouteErrorFallback({ error }: ErrorComponentProps) {
  useEffect(() => {
    const failure = error instanceof Error ? error : new Error(String(error));
    reportClientError({ kind: "render", message: failure.message, stack: failure.stack });
  }, [error]);
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4">
      <p className="text-muted-foreground">Algo deu errado ao carregar esta página.</p>
      <a href="/" className="text-primary hover:underline">
        Voltar para o início
      </a>
    </div>
  );
}

// Create a new router instance
export const router = createRouter({
  routeTree,
  defaultErrorComponent: RouteErrorFallback,
  defaultPreload: "intent",
  defaultPreloadStaleTime: 60_000,
  defaultNotFoundComponent: () => {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">Página não encontrada</p>
        <a href="/" className="text-primary hover:underline">
          Voltar para o início
        </a>
      </div>
    );
  },
});

// Register the router instance for type safety
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
