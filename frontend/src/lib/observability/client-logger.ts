/**
 * Erros do navegador → log do backend (`POST /client-logs`, padrão da frota 2026-10-22).
 *
 * Todo erro que o usuário VÊ (via `notifyError`) e todo erro que ninguém viu (`window.onerror`,
 * `unhandledrejection`, `errorComponent` do router) entra aqui. O backend grava uma linha
 * `client_error` com o `request_id` da resposta que falhou, então o suporte acha a linha do
 * backend a partir do código mostrado no toast.
 *
 * Fila em memória com envio em lote. O que não pôde sair (offline, servidor fora) vai para um
 * buffer em `localStorage` e é reenviado no `online` e no próximo boot: o erro "só do navegador"
 * também chega, só que depois. O envio usa `fetch` cru de propósito: passar pelo `ApiClient`
 * faria uma falha do próprio envio virar mais um erro reportado (loop).
 */

export type ClientLogKind = "api_error" | "network" | "unhandled" | "render" | "toast";

export interface ClientLogEvent {
  level: "error" | "warning";
  kind: ClientLogKind;
  title?: string;
  message: string;
  stack?: string;
  route: string;
  requestId?: string;
  status?: number;
  appVersion?: string;
  occurredAt: string;
}

export type ClientLogInput = Omit<
  ClientLogEvent,
  "route" | "occurredAt" | "appVersion" | "level"
> & {
  level?: ClientLogEvent["level"];
};

const ENDPOINT = "/api/v1/client-logs";
export const CLIENT_LOG_BUFFER_KEY = "client-logs:pending";
const FLUSH_DELAY_MS = 5_000;
const FLUSH_BATCH_SIZE = 10;
/** Teto do backend por lote (`MAX_EVENTS_PER_BATCH`). */
const MAX_BATCH = 20;
/** Teto do buffer persistido: o mais antigo sai primeiro. */
const MAX_BUFFERED = 50;
const DEDUP_WINDOW_MS = 30_000;
/** Limites do schema do backend — cortar aqui evita um 422 que perderia o lote inteiro. */
const MAX_MESSAGE = 500;
const MAX_STACK = 4_000;
const MAX_ROUTE = 300;

type Sender = (events: ClientLogEvent[], useBeacon: boolean) => Promise<boolean>;

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

interface ClientLoggerDeps {
  send: Sender;
  storage: () => StorageLike | null;
  now: () => number;
  route: () => string;
  appVersion: string;
}

function truncate(value: string | undefined, max: number): string | undefined {
  return value && value.length > max ? value.slice(0, max) : value;
}

function toWire(event: ClientLogEvent): Record<string, unknown> {
  return {
    level: event.level,
    kind: event.kind,
    title: event.title,
    message: event.message,
    stack: event.stack,
    route: event.route,
    request_id: event.requestId,
    status: event.status,
    app_version: event.appVersion,
    occurred_at: event.occurredAt,
  };
}

/** Envio padrão: `sendBeacon` quando a página está saindo (sem header → anônimo),
 *  `fetch keepalive` no resto. `false` = não chegou, volta para o buffer. */
const sendToBackend: Sender = async (events, useBeacon) => {
  const body = JSON.stringify({ events: events.map(toWire) });
  if (useBeacon && typeof navigator !== "undefined" && navigator.sendBeacon) {
    return navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "application/json" }));
  }
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // O template não tem token store (identidade aberta): o envio é anônimo. App com auth lê o
  // token em memória aqui e manda `Authorization` para o backend anotar o `user_id`.
  try {
    const response = await fetch(ENDPOINT, {
      method: "POST",
      headers,
      body,
      keepalive: true,
      credentials: "include",
    });
    // 4xx = o lote nunca vai passar (schema); descartar em vez de reenviar para sempre.
    return response.ok || (response.status >= 400 && response.status < 500);
  } catch {
    return false;
  }
};

export function createClientLogger(deps: ClientLoggerDeps) {
  let queue: ClientLogEvent[] = [];
  let timer: ReturnType<typeof setTimeout> | null = null;
  const recent = new Map<string, number>();

  function readBuffer(): ClientLogEvent[] {
    try {
      const raw = deps.storage()?.getItem(CLIENT_LOG_BUFFER_KEY);
      const parsed: unknown = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? (parsed as ClientLogEvent[]) : [];
    } catch {
      return [];
    }
  }

  function writeBuffer(events: ClientLogEvent[]): void {
    try {
      const storage = deps.storage();
      if (!storage) return;
      if (events.length === 0) storage.removeItem(CLIENT_LOG_BUFFER_KEY);
      else storage.setItem(CLIENT_LOG_BUFFER_KEY, JSON.stringify(events.slice(-MAX_BUFFERED)));
    } catch {
      // Storage cheio/bloqueado: o evento se perde, a tela não.
    }
  }

  function isDuplicate(event: ClientLogEvent): boolean {
    const key = `${event.kind}|${event.route}|${event.message}`;
    const now = deps.now();
    const last = recent.get(key);
    recent.set(key, now);
    return last !== undefined && now - last < DEDUP_WINDOW_MS;
  }

  async function flush(useBeacon = false): Promise<void> {
    if (timer) clearTimeout(timer);
    timer = null;
    const pending = [...readBuffer(), ...queue];
    queue = [];
    writeBuffer([]);
    if (pending.length === 0) return;
    const unsent: ClientLogEvent[] = [];
    for (let i = 0; i < pending.length; i += MAX_BATCH) {
      const batch = pending.slice(i, i + MAX_BATCH);
      if (!(await deps.send(batch, useBeacon))) unsent.push(...batch);
    }
    if (unsent.length > 0) writeBuffer([...readBuffer(), ...unsent]);
  }

  function report(input: ClientLogInput): void {
    // 401 é o fluxo de sessão (refresh + login), não um erro de produto.
    if (input.status === 401) return;
    const event: ClientLogEvent = {
      ...input,
      level: input.level ?? "error",
      title: truncate(input.title, MAX_MESSAGE),
      message: truncate(input.message, MAX_MESSAGE) || "(sem mensagem)",
      stack: truncate(input.stack, MAX_STACK),
      route: truncate(deps.route(), MAX_ROUTE) ?? "/",
      appVersion: deps.appVersion,
      occurredAt: new Date(deps.now()).toISOString(),
    };
    if (isDuplicate(event)) return;
    queue.push(event);
    if (queue.length >= FLUSH_BATCH_SIZE) void flush();
    else if (!timer) timer = setTimeout(() => void flush(), FLUSH_DELAY_MS);
  }

  return { report, flush };
}

function safeLocalStorage(): StorageLike | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

const clientLogger = createClientLogger({
  send: sendToBackend,
  storage: safeLocalStorage,
  now: () => Date.now(),
  // Só o path: a query string pode carregar busca digitada pelo usuário.
  route: () => (typeof location === "undefined" ? "/" : location.pathname),
  appVersion: typeof __APP_BUILD_ID__ === "string" ? __APP_BUILD_ID__ : "dev",
});

export const reportClientError = clientLogger.report;
export const flushClientLogs = clientLogger.flush;

/** Erros já reportados por `notifyError`: o mesmo objeto rejeitado sem `catch` (o `mutateAsync`
 *  que ninguém tratou) não vira uma segunda linha como `unhandled`. */
const reportedErrors = new WeakSet<object>();

export function markErrorReported(error: unknown): void {
  if (typeof error === "object" && error !== null) reportedErrors.add(error);
}

function wasErrorReported(error: unknown): boolean {
  return typeof error === "object" && error !== null && reportedErrors.has(error);
}

function describeUnknown(reason: unknown): { message: string; stack?: string } {
  if (reason instanceof Error) return { message: reason.message, stack: reason.stack };
  return { message: typeof reason === "string" ? reason : (JSON.stringify(reason) ?? "") };
}

/**
 * Instala a captura global UMA vez no boot (`main.tsx`): erro não tratado, promise rejeitada
 * sem `catch`, flush ao esconder a página e reenvio ao voltar a rede (e do buffer do boot).
 */
export function installClientErrorCapture(): void {
  window.addEventListener("error", (event) => {
    reportClientError({ kind: "unhandled", ...describeUnknown(event.error ?? event.message) });
  });
  window.addEventListener("unhandledrejection", (event) => {
    if (wasErrorReported(event.reason)) return;
    reportClientError({ kind: "unhandled", ...describeUnknown(event.reason) });
  });
  window.addEventListener("online", () => void flushClientLogs());
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") void flushClientLogs(true);
  });
  void flushClientLogs();
}
