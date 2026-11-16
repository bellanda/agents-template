/**
 * The fleet's ONE resilient SSE loop (audit 2026-11-13 core-spa-06). Framework-free so it can be
 * tested with fake timers; `use-resilient-stream.ts` wraps it for React.
 *
 * What it adds over a plain "reconnect when the read fails" loop:
 * - WATCHDOG: no byte (heartbeat included) for `idleTimeoutMs` (45 s = two 20 s server heartbeats
 *   plus slack) aborts the attempt and reopens. A half-open connection (phone locked, Wi-Fi swap,
 *   a proxy holding the buffer) never fails: the pending `reader.read()` just never returns.
 * - VISIBILITY: coming back to the foreground after more than `hiddenReopenAfterMs` hidden
 *   reopens the stream even though it looks healthy (mobile browsers freeze the socket).
 * - RESYNC on EVERY reopen: there is no replay on the server, so whatever happened while the
 *   stream was down is only seen by refetching. `onResync` runs when the new connection is OPEN
 *   (`onOpen`), never before — resyncing earlier leaves a gap where events are neither refetched
 *   nor streamed. Only the very first attempt skips it (the queries just loaded).
 * - Reconnect schedule: exponential backoff + jitter (`reconnect.ts`), cut short by the browser's
 *   `online` event or the tab becoming visible. Watchdog/visibility reopens do not back off.
 * - Auth: 401/403 ask `refreshToken` (single-flight in the app's ApiClient) because an idle single
 *   tab never rotates the token by itself; a dead session (refresh answers 401/403) stops hammering.
 *
 * The transport (`open`) MUST: resolve when the stream ends or is aborted (swallow AbortError),
 * call `onOpen` once the response is accepted, call `onActivity` for every chunk (see
 * `sse-reader.ts`), and report failures through `onError` or by throwing (`status` on the error
 * lets the loop tell "token expired" from "backend down").
 */
import { reconnectDelayMs } from "./reconnect";

export const STREAM_IDLE_TIMEOUT_MS = 45_000;
export const HIDDEN_REOPEN_AFTER_MS = 30_000;

export interface StreamOpenArgs {
  accessToken: string;
  signal: AbortSignal;
  /** Response accepted (HTTP 200 + body): the connection is live. */
  onOpen: () => void;
  /** Bytes arrived (a heartbeat counts). */
  onActivity: () => void;
  onError: (error: unknown) => void;
}

export interface ResilientStreamOptions {
  open: (args: StreamOpenArgs) => Promise<void>;
  /** Fresh token on every attempt (rotation between reconnects). */
  getAccessToken: () => string | null;
  /** Token used when the store is empty at attempt time. */
  fallbackAccessToken: string;
  refreshToken?: () => Promise<unknown>;
  /** Statuses that mean "token expired, refresh then retry". Default 401 + 403. */
  refreshOnStatuses?: readonly number[];
  /** Statuses that mean "retrying is pointless" (e.g. 403 = lost the permission). */
  stopOnStatuses?: readonly number[];
  /** Refetch everything the stream would have delivered. Runs on every reopen but the first. */
  onResync?: () => void;
  /**
   * The first open of THIS loop also resyncs: a previous loop (same hook, token rotated) had
   * already been connected, so the gap between the two connections is a reconnect, not a cold
   * start (audit 2026-11-15 r2-kailos-fe-hooks-lib-01).
   */
  resyncOnFirstOpen?: boolean;
  idleTimeoutMs?: number;
  hiddenReopenAfterMs?: number;
  random?: () => number;
}

const statusOf = (error: unknown): number => (error as { status?: number } | null)?.status ?? 0;

/** Resolves when `signal` aborts (or already has). */
function whenAborted(signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) resolve();
    else signal.addEventListener("abort", () => resolve(), { once: true });
  });
}

/** Resolves after `ms`, or as soon as the browser is back online / visible / the loop stops. */
function waitBeforeRetry(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const finish = () => {
      clearTimeout(timer);
      window.removeEventListener("online", finish);
      document.removeEventListener("visibilitychange", onVisibility);
      signal.removeEventListener("abort", finish);
      resolve();
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") finish();
    };
    const timer = setTimeout(finish, ms);
    window.addEventListener("online", finish);
    document.addEventListener("visibilitychange", onVisibility);
    signal.addEventListener("abort", finish);
  });
}

/** Starts the loop; returns the stop function (call it on unmount). */
export function startResilientStream(options: ResilientStreamOptions): () => void {
  const {
    open,
    getAccessToken,
    fallbackAccessToken,
    refreshToken,
    refreshOnStatuses = [401, 403],
    stopOnStatuses = [],
    onResync,
    resyncOnFirstOpen = false,
    idleTimeoutMs = STREAM_IDLE_TIMEOUT_MS,
    hiddenReopenAfterMs = HIDDEN_REOPEN_AFTER_MS,
    random,
  } = options;

  const stopController = new AbortController();
  let current: AbortController | null = null;
  let reopenRequested = false;
  let hiddenSince: number | null = null;

  const requestReopen = () => {
    reopenRequested = true;
    current?.abort();
  };

  const onVisibility = () => {
    if (document.visibilityState === "hidden") {
      hiddenSince = Date.now();
      return;
    }
    const wasHiddenFor = hiddenSince === null ? 0 : Date.now() - hiddenSince;
    hiddenSince = null;
    if (wasHiddenFor > hiddenReopenAfterMs) requestReopen();
  };
  document.addEventListener("visibilitychange", onVisibility);

  const run = async () => {
    let attemptNumber = 0;
    let failures = 0;
    while (!stopController.signal.aborted) {
      attemptNumber += 1;
      const isFirstAttempt = attemptNumber === 1;
      const attempt = new AbortController();
      current = attempt;
      reopenRequested = false;
      let failureStatus = 0;

      let watchdog: ReturnType<typeof setTimeout> | undefined;
      const armWatchdog = () => {
        clearTimeout(watchdog);
        watchdog = setTimeout(requestReopen, idleTimeoutMs);
      };
      armWatchdog();

      // Raced against the abort so a transport that ignores the signal (a `read()` that never
      // settles — the exact half-open case) cannot park the loop forever.
      try {
        await Promise.race([
          open({
            accessToken: getAccessToken() ?? fallbackAccessToken,
            signal: attempt.signal,
            // A transport that ignores the abort signal may still call back after this attempt
            // was replaced; a stale callback must not re-arm a watchdog nor resync a second time
            // (review of audit 2026-11-13 core-spa-06).
            onOpen: () => {
              if (attempt.signal.aborted) return;
              failures = 0;
              armWatchdog();
              if (!isFirstAttempt || resyncOnFirstOpen) onResync?.();
            },
            onActivity: () => {
              if (!attempt.signal.aborted) armWatchdog();
            },
            onError: (error) => {
              failureStatus = statusOf(error);
            },
          }),
          whenAborted(attempt.signal),
        ]);
      } catch (error) {
        failureStatus = statusOf(error);
      }
      clearTimeout(watchdog);
      attempt.abort();
      current = null;
      if (stopController.signal.aborted) return;
      // Watchdog / foreground reopen: the connection was healthy-looking, not failing — no backoff.
      if (reopenRequested) continue;

      if (stopOnStatuses.includes(failureStatus)) return;
      if (refreshToken && refreshOnStatuses.includes(failureStatus)) {
        try {
          await refreshToken();
        } catch (error) {
          // Dead session: stop hammering; the reactive token dep reopens on the next login.
          if (refreshOnStatuses.includes(statusOf(error))) return;
        }
        if (stopController.signal.aborted) return;
      }
      await waitBeforeRetry(reconnectDelayMs(failures, random), stopController.signal);
      failures += 1;
    }
  };
  void run();

  return () => {
    document.removeEventListener("visibilitychange", onVisibility);
    stopController.abort();
    current?.abort();
  };
}
