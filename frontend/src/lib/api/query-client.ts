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

/**
 * Política de frescor da frota (decisão do usuário 2026-11-13, auditoria core-spa-01): o
 * PADRÃO é dado fresco. `staleTime` 30 s + refetch ao voltar o foco/a rede fazem a tela
 * renovar sozinha sem F5 (antes: 5 min e foco desligado, a maior causa de "preciso dar F5").
 * Cache longo no front é escolha CONSCIENTE de uma query (catálogo estático, vocabulário):
 * `staleTime` explícito na própria query + comentário dizendo o porquê. Nunca suba o default.
 *
 * O foco só refaz query ATIVA e velha, então o custo é baixo. Formulário que copia a query
 * para estado local usa `useSyncedDraft` para o refetch não apagar o que a pessoa digita.
 */
export const DEFAULT_STALE_TIME_MS = 30_000;
const GC_TIME_MS = 10 * 60 * 1000;
const QUERY_RETRIES = 3;
const THROTTLED_STATUSES = new Set([408, 429]);

function clientErrorStatus(error: unknown): number | null {
  if (!error || typeof error !== "object" || !("status" in error)) return null;
  const status = (error as { status: unknown }).status;
  return typeof status === "number" && status >= 400 && status < 500 ? status : null;
}

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
        staleTime: DEFAULT_STALE_TIME_MS,
        gcTime: GC_TIME_MS,
        // 4xx não melhora repetindo (exceto 408/429, com teto menor); rede/5xx tenta de novo.
        retry: (failureCount, error: unknown) => {
          const status = clientErrorStatus(error);
          if (status !== null) {
            return THROTTLED_STATUSES.has(status) ? failureCount < 2 : false;
          }
          return failureCount < QUERY_RETRIES;
        },
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
      },
      mutations: {
        // Mutation NUNCA é repetida sozinha (auditoria 2026-11-13: POST não idempotente
        // duplicou mensagem de WhatsApp, baixa financeira e execução paga de agente quando a
        // resposta se perdeu em 502/timeout). Quem é idempotente (PUT/DELETE) liga `retry`
        // na própria mutation, com comentário.
        retry: false,
      },
    },
  });
}
