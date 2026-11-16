/** Reconnect schedule for the app stream: exponential, capped, with jitter. */
export const RECONNECT_BASE_MS = 1_000;
export const RECONNECT_CAP_MS = 30_000;

/**
 * `attempt` 0 = first retry. Delay doubles from 1 s up to the 30 s cap; jitter keeps it in
 * [delay/2, delay] so a backend restart doesn't make every open tab reconnect in the same instant.
 */
export function reconnectDelayMs(attempt: number, random: () => number = Math.random): number {
  const ceiling = Math.min(RECONNECT_CAP_MS, RECONNECT_BASE_MS * 2 ** attempt);
  return Math.round(ceiling / 2 + (ceiling / 2) * random());
}
