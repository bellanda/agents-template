import { DEFAULT_STALE_TIME_MS, createAppQueryClient } from "@/lib/api/query-client";
import { QueryObserver, focusManager, onlineManager } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn() } }));
vi.mock("@/lib/observability/client-logger", () => ({
  reportClientError: vi.fn(),
  markErrorReported: vi.fn(),
}));

afterEach(() => {
  vi.useRealTimers();
  focusManager.setFocused(undefined);
  onlineManager.setOnline(true);
});

describe("defaults de frescor do QueryClient (core-spa-01)", () => {
  it("dado fresco por padrão: 30 s, refetch ao voltar foco e rede", () => {
    const { queries } = createAppQueryClient().getDefaultOptions();
    expect(DEFAULT_STALE_TIME_MS).toBe(30_000);
    expect(queries?.staleTime).toBe(30_000);
    expect(queries?.refetchOnWindowFocus).toBe(true);
    expect(queries?.refetchOnReconnect).toBe(true);
  });

  it("query montada e velha refaz sozinha quando a aba volta ao foco", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    const client = createAppQueryClient();
    client.mount(); // liga os listeners de foco/rede (o QueryClientProvider faz isso na app)
    const queryFn = vi.fn().mockResolvedValue("dado");
    const observer = new QueryObserver(client, { queryKey: ["tela"], queryFn });
    const unsubscribe = observer.subscribe(() => {});
    await vi.waitFor(() => expect(observer.getCurrentResult().isSuccess).toBe(true));

    // Ainda fresca: voltar ao foco não custa request.
    focusManager.setFocused(false);
    focusManager.setFocused(true);
    expect(queryFn).toHaveBeenCalledTimes(1);

    vi.setSystemTime(Date.now() + DEFAULT_STALE_TIME_MS + 1);
    focusManager.setFocused(false);
    focusManager.setFocused(true);
    // `vi.waitFor` mede o timeout por Date (falsa e adiantada): espera em tempo real.
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(queryFn).toHaveBeenCalledTimes(2);
    unsubscribe();
    client.unmount();
  });
});

describe("mutation não é repetida sozinha (akmeo-fe-all-06 e irmãos)", () => {
  it.each([502, 503, 504, 500])("POST que falha com %i roda uma única vez", async (status) => {
    const client = createAppQueryClient();
    const mutationFn = vi.fn().mockRejectedValue({ status, message: "falha" });
    const mutation = client
      .getMutationCache()
      .build(client, { mutationFn, meta: { silentError: true } });
    await mutation.execute(undefined).catch(() => {});
    expect(mutationFn).toHaveBeenCalledTimes(1);
  });

  it("erro de rede (sem status) também roda uma única vez", async () => {
    const client = createAppQueryClient();
    const mutationFn = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const mutation = client
      .getMutationCache()
      .build(client, { mutationFn, meta: { silentError: true } });
    await mutation.execute(undefined).catch(() => {});
    expect(mutationFn).toHaveBeenCalledTimes(1);
  });

  it("mutation idempotente ainda pode ligar retry explícito", async () => {
    const client = createAppQueryClient();
    const mutationFn = vi.fn().mockRejectedValueOnce({ status: 503 }).mockResolvedValue("ok");
    const mutation = client
      .getMutationCache()
      .build(client, { mutationFn, retry: 1, retryDelay: 0, meta: { silentError: true } });
    await expect(mutation.execute(undefined)).resolves.toBe("ok");
    expect(mutationFn).toHaveBeenCalledTimes(2);
  });
});
