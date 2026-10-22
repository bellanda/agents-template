import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { FALLBACK_ERROR_TITLE, FALLBACK_QUERY_ERROR_TITLE, notifyError } from "./notify";

/**
 * QueryClient do app — defaults + o piso de visibilidade de erro (padrão da frota, 2026-10-22).
 *
 * Query/mutation que falha sem `onError` local ficaria calada. Aqui toda falha vira toast
 * (título da ação + motivo do backend, via `notifyError`) e linha no log do backend.
 *
 * Mutation: título em `meta.errorTitle` ("Não foi possível salvar a configuração"). A tela NÃO
 * mostra toast no `onError`/`catch`: se quiser título mais específico, chama `notifyError` com o
 * MESMO erro e o toast é substituído (id por erro), nunca duplicado.
 */

declare module "@tanstack/react-query" {
  interface Register {
    queryMeta: AppQueryMeta;
    mutationMeta: AppQueryMeta;
  }
}

export interface AppQueryMeta extends Record<string, unknown> {
  /** Ação que falhou, no formato "Não foi possível <verbo> <objeto>". */
  errorTitle?: string;
  /** A tela já mostra o erro inline (ou ele é esperado): sem toast global. */
  silentError?: boolean;
}

const STALE_TIME_MS = 60_000;

export function createAppQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (query.meta?.silentError) return;
        // `id` estável por query: polling que falha fica em UM toast em vez de uma pilha.
        notifyError(query.meta?.errorTitle ?? FALLBACK_QUERY_ERROR_TITLE, error, {
          id: `query-error:${query.queryHash}`,
        });
      },
    }),
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        if (mutation.meta?.silentError) return;
        notifyError(mutation.meta?.errorTitle ?? FALLBACK_ERROR_TITLE, error);
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: STALE_TIME_MS,
        refetchOnWindowFocus: false,
      },
    },
  });
}
