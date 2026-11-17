/**
 * Mundo de teste de tela de CRUD do template: liga o fake de API com memória (`fake-api.ts`,
 * canônico da frota) às duas formas de a tela falar com o backend. Cada app tem o seu, porque o
 * contexto difere (o template não tem login nem permissões).
 *
 * - Tela que usa `useDataProvider()` (`useCrud`): `vi.mock("@/lib/api/context", () => ({
 *   useDataProvider: () => world.ctx }))` com o `ctx` de `makeCrudWorld`.
 * - Tela que fala por `apiFetch` (`lib/api.ts`: agent-config, threads): `stubFetchFromFakeApi(api)`
 *   troca o `fetch` global por um que despacha no mesmo fake e devolve `Response` real (erro do
 *   fake vira status + `{detail}`, como o FastAPI).
 *
 * ```ts
 * const { api, ctx } = makeCrudWorld({ collections: { "/contacts": rows } });
 * ```
 */
import { createAppQueryClient } from "@/lib/api/query-client";
import { CrudService } from "@/lib/api/services/crud";
import { createFakeApi, type FakeApiOptions, type FakeMethod } from "@/test/fake-api";
import { vi } from "vitest";

const API_PREFIX = "/api/v1";
const HTTP_NO_CONTENT = 204;
const HTTP_SERVER_ERROR = 500;

export function makeCrudWorld(options: FakeApiOptions) {
  const api = createFakeApi(options);
  const ctx = {
    client: api.client,
    createCrudService: (endpoint: string) => new CrudService(api.client as never, endpoint),
  };
  return { api, ctx };
}

export type CrudWorld = ReturnType<typeof makeCrudWorld>;

function asFakeFailure(error: unknown): { status: number; message: string } | null {
  if (typeof error !== "object" || error === null) return null;
  const { status, message } = error as { status?: unknown; message?: unknown };
  return typeof status === "number" ? { status, message: String(message ?? "") } : null;
}

/** `fetch` global dispatching on the fake API; the `/api/v1` prefix is stripped before routing. */
export function stubFetchFromFakeApi(api: CrudWorld["api"]): void {
  vi.stubGlobal(
    "fetch",
    async (input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> => {
      const url = String(input).replace(API_PREFIX, "");
      const method = (init.method ?? "GET").toUpperCase() as FakeMethod;
      const body = typeof init.body === "string" ? JSON.parse(init.body) : undefined;
      try {
        const result = await api.client[
          method.toLowerCase() as "get" | "post" | "put" | "patch" | "delete"
        ](url, body);
        if (result.data === null) return new Response(null, { status: HTTP_NO_CONTENT });
        return Response.json(result.data, { status: result.status });
      } catch (error) {
        const failure = asFakeFailure(error);
        if (!failure) throw error;
        return Response.json(
          { detail: failure.message },
          { status: failure.status || HTTP_SERVER_ERROR }
        );
      }
    }
  );
}

/**
 * The app's REAL QueryClient (staleTime 30 s, global mutation error toast), minus refetch on
 * window focus/reconnect: in jsdom focus returns when a dialog closes and would refetch the list
 * by itself, hiding a mutation that forgot to invalidate. A bare `new QueryClient()` (staleTime 0)
 * hides the same bug because a remounted screen refetches anyway.
 */
export function makeCrudQueryClient() {
  const queryClient = createAppQueryClient();
  const defaults = queryClient.getDefaultOptions();
  queryClient.setDefaultOptions({
    ...defaults,
    queries: { ...defaults.queries, refetchOnWindowFocus: false, refetchOnReconnect: false },
  });
  return queryClient;
}
