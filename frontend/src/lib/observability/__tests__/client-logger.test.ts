import { CLIENT_LOG_BUFFER_KEY, createClientLogger } from "@/lib/observability/client-logger";
import { beforeEach, describe, expect, it, vi } from "vitest";

function memoryStorage() {
  const data = new Map<string, string>();
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
  };
}

let clock = 0;
let storage = memoryStorage();
const send = vi.fn();

function makeLogger() {
  return createClientLogger({
    send,
    storage: () => storage,
    now: () => clock,
    route: () => "/organizations/x/portais",
    appVersion: "build-1",
  });
}

describe("client-logger", () => {
  beforeEach(() => {
    clock = 1_000_000;
    storage = memoryStorage();
    send.mockReset();
  });

  it("manda em lote com rota e versão; 401 e repetição em 30 s ficam de fora", async () => {
    send.mockResolvedValue(true);
    const logger = makeLogger();

    logger.report({ kind: "api_error", message: "Portal ainda não liberado.", status: 409 });
    logger.report({ kind: "api_error", message: "Portal ainda não liberado.", status: 409 });
    logger.report({ kind: "api_error", message: "Sessão expirada.", status: 401 });
    logger.report({ kind: "unhandled", message: "x is undefined" });
    await logger.flush();

    expect(send).toHaveBeenCalledTimes(1);
    const [events] = send.mock.calls[0]!;
    expect(events).toHaveLength(2);
    expect(events[0]).toMatchObject({
      kind: "api_error",
      route: "/organizations/x/portais",
      appVersion: "build-1",
      level: "error",
    });
  });

  it("o que não chegou fica no buffer e sai no próximo flush (offline → online)", async () => {
    const logger = makeLogger();
    send.mockResolvedValueOnce(false);
    logger.report({ kind: "network", message: "Sem conexão com o servidor." });
    await logger.flush();

    expect(storage.getItem(CLIENT_LOG_BUFFER_KEY)).toContain("Sem conexão");

    send.mockResolvedValueOnce(true);
    await makeLogger().flush();

    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1]![0]).toHaveLength(1);
    expect(storage.getItem(CLIENT_LOG_BUFFER_KEY)).toBeNull();
  });

  it("corta mensagem e stack no limite do backend em vez de perder o lote num 422", async () => {
    send.mockResolvedValue(true);
    const logger = makeLogger();
    logger.report({ kind: "unhandled", message: "m".repeat(900), stack: "s".repeat(9_000) });
    await logger.flush();

    const [event] = send.mock.calls[0]![0];
    expect(event.message).toHaveLength(500);
    expect(event.stack).toHaveLength(4_000);
  });
});
