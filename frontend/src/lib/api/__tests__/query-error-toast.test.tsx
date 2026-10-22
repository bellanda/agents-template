// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { notifyError } from "@/lib/api/notify";
import { createAppQueryClient } from "@/lib/api/query-client";
import { reportClientError } from "@/lib/observability/client-logger";
import { type QueryClient, QueryClientProvider, useMutation } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
}));
vi.mock("@/lib/observability/client-logger", () => ({
  reportClientError: vi.fn(),
  markErrorReported: vi.fn(),
}));

const errorToast = vi.mocked(toast.error);
const reported = vi.mocked(reportClientError);

interface ApiError {
  status: number;
  message: string;
  requestId?: string;
}

function apiError(status: number, message: string, requestId?: string): ApiError {
  return { status, message, requestId };
}

let queryClient: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

/** Roda uma query que falha e devolve o controle só depois do `onError` da cache. */
async function failingQuery(error: unknown, meta?: Record<string, unknown>) {
  await queryClient
    .fetchQuery({ queryKey: ["falha", error], queryFn: () => Promise.reject(error), meta })
    .catch(() => {});
}

/** Ids dos toasts de erro: chamadas com o mesmo id são UM toast na tela (o sonner substitui). */
function visibleErrorToasts(): number {
  return new Set(errorToast.mock.calls.map(([, options]) => (options as { id?: string })?.id)).size;
}

function lastToast(): { title: unknown; description: unknown } {
  const [title, options] = errorToast.mock.calls.at(-1)!;
  return { title, description: (options as { description?: unknown })?.description };
}

describe("rede de segurança de erro do QueryClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createAppQueryClient();
  });

  it("query que falha avisa com título + motivo do backend, e vai para o log", async () => {
    await failingQuery(apiError(403, "Sem acesso às instruções deste agente."), {
      errorTitle: "Não foi possível carregar as instruções",
    });

    expect(errorToast).toHaveBeenCalledTimes(1);
    expect(lastToast().title).toBe("Não foi possível carregar as instruções");
    expect(String(lastToast().description)).toBe("Sem acesso às instruções deste agente.");
    expect(reported).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "api_error", status: 403 })
    );
  });

  it("usa um id estável por query — polling que falha não empilha toast", async () => {
    const error = apiError(404, "Instruções não encontradas");
    await failingQuery(error);
    queryClient.removeQueries({ queryKey: ["falha", error] });
    await failingQuery(error);

    expect(visibleErrorToasts()).toBe(1);
    const id = (errorToast.mock.calls[0]![1] as { id: string }).id;
    expect(id).toContain("query-error:");
  });

  it("401 fica calado — quem trata é o refresh/logout, e o toast duplicaria o aviso", async () => {
    await failingQuery(apiError(401, "Not authenticated"));

    expect(errorToast).not.toHaveBeenCalled();
    expect(reported).not.toHaveBeenCalled();
  });

  it("`meta.silentError` é a escotilha de quem já mostra o erro inline", async () => {
    await failingQuery(apiError(409, "Erro no servidor"), { silentError: true });

    expect(errorToast).not.toHaveBeenCalled();
  });

  it("mutation usa `meta.errorTitle` como título e o motivo do backend como descrição", async () => {
    const { result } = renderHook(
      () =>
        useMutation({
          mutationFn: () => Promise.reject(apiError(409, "Portal ainda não liberado.")),
          meta: { errorTitle: "Não foi possível iniciar a autorização" },
        }),
      { wrapper }
    );

    await act(async () => {
      await result.current.mutateAsync().catch(() => {});
    });

    expect(errorToast).toHaveBeenCalledTimes(1);
    expect(lastToast()).toEqual({
      title: "Não foi possível iniciar a autorização",
      description: "Portal ainda não liberado.",
    });
  });

  // Regressão 2026-10-22 (Portais → "Autorizar"): o global rodava antes do `catch` da tela e
  // saíam dois toasts. Agora a tela SUBSTITUI o toast global do mesmo erro.
  it("tela que trata o erro (catch ou onError) substitui o toast global — sobra um", async () => {
    const failure = apiError(409, "Portal ainda não liberado.");
    const { result } = renderHook(
      () => useMutation({ mutationFn: () => Promise.reject(failure) }),
      { wrapper }
    );

    await act(async () => {
      try {
        await result.current.mutateAsync();
      } catch (err) {
        notifyError("Não foi possível iniciar a autorização", err);
      }
    });
    await act(async () => {
      result.current.mutate(undefined, {
        onError: (err) => notifyError("Não foi possível iniciar a autorização", err),
      });
    });

    expect(visibleErrorToasts()).toBe(1);
    expect(lastToast().title).toBe("Não foi possível iniciar a autorização");
    // Uma linha de log por falha, mesmo com o toast trocado de título.
    expect(reported).toHaveBeenCalledTimes(1);
  });

  it("erro 5xx mostra o código curto do request_id para o suporte", () => {
    notifyError(
      "Não foi possível salvar as instruções",
      apiError(500, "Erro interno.", "abcdef1234567890")
    );

    expect(lastToast().description).toBe("Erro interno. (código abcdef12)");
  });
});
