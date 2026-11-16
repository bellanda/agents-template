import { getAccessToken } from "@/lib/api/access-token-store";

/**
 * The ONLY place that calls `fetch` for our own API (guarded by `__tests__/no-raw-fetch.test.ts`).
 * Audit 2026-11-13 template-gap-03: the template's chat, uploads and agent-config used raw `fetch`
 * with an `X-User-Id` header, so as soon as an app gained a real login (short-lived access token
 * in memory) every one of those screens broke at token expiry — they never attached the Bearer
 * nor renewed the session. Raw `fetch` stays only for external URLs and the allowlisted cases.
 *
 * Contract:
 * - `Authorization: Bearer <token>` from the in-memory store. With no session the caller's
 *   `userId` is sent as the token instead: the template backend (`services/auth.py`, OPEN in
 *   local/test only) resolves a bearer AS the user id, so the stub keeps working unchanged.
 * - 401 → one single-flight session refresh (`registerSessionRefresher`), then ONE retry with the
 *   renewed token. 5xx / 429 / network failures never trigger it (they do not mean "session over").
 * - Returns the raw `Response`: callers keep their own `ok`/error handling.
 */
export type SessionRefresher = () => Promise<boolean>;

let sessionRefresher: SessionRefresher | null = null;
let refreshInFlight: Promise<boolean> | null = null;

/** The app's auth layer registers how to renew the session (e.g. POST /auth/token). */
export function registerSessionRefresher(refresher: SessionRefresher | null): void {
  sessionRefresher = refresher;
  refreshInFlight = null;
}

/**
 * N requests that take a 401 together share ONE refresh (rotating refresh tokens break otherwise).
 * `ApiClient` (api-client.ts) goes through this same function, so `apiFetch` and `ApiClient`
 * callers hitting 401 together still trigger a single renewal.
 */
export function refreshSession(): Promise<boolean> {
  if (!sessionRefresher) return Promise.resolve(false);
  if (refreshInFlight) return refreshInFlight;
  const inFlight = sessionRefresher()
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });
  refreshInFlight = inFlight;
  return inFlight;
}

function withAuthorization(init: RequestInit, userId: string | undefined): RequestInit {
  const token = getAccessToken() ?? userId ?? null;
  if (!token) return init;
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return { ...init, headers };
}

export interface ApiFetchOptions {
  /** Open-identity fallback (local/test stub): sent as the bearer when no session token exists. */
  userId?: string;
}

export async function apiFetch(
  url: string,
  init: RequestInit = {},
  { userId }: ApiFetchOptions = {}
): Promise<Response> {
  const response = await fetch(url, withAuthorization(init, userId));
  if (response.status !== 401 || !sessionRefresher) return response;
  if (!(await refreshSession())) return response;
  return fetch(url, withAuthorization(init, userId));
}
