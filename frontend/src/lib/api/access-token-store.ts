/**
 * In-memory access token (audit 2026-11-13 template-gap-03). NEVER persisted to localStorage
 * (XSS). Same contract as the fleet apps' `access-token-store`, minus the cross-tab
 * BroadcastChannel: add it together with the real auth backend (see kailos).
 *
 * The template ships no login, so this is empty until the app's auth store calls
 * `setAccessToken(...)`; `apiFetch` falls back to the open-identity stub (token = user id).
 */
let accessToken: string | null = null;
const listeners = new Set<() => void>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  listeners.forEach((listener) => listener());
}

export function subscribeAccessToken(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
