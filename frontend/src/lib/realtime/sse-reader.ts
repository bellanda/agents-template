/**
 * Shared SSE body reader (fleet standard, audit 2026-11-13 core-spa-06). `EventSource` cannot
 * attach an Authorization header, so every app opens the stream with `fetch` and reads the body
 * here. Frames are separated by a blank line; only `data:` lines are delivered (heartbeats start
 * with ":" and are dropped), but EVERY chunk calls `onActivity` — that is what the watchdog in
 * `resilient-stream.ts` measures to tell a live-but-quiet stream from a dead connection.
 *
 * Resolves when the server ends the stream. Abort/network errors reject (the caller owns them).
 */
export interface SseReadOptions {
  /** Raw payload after `data:` (callers JSON-parse and key-transform it). */
  onData: (payload: string) => void;
  /** Any bytes arrived, heartbeat included. */
  onActivity?: () => void;
}

export async function readSseBody(
  body: ReadableStream<Uint8Array>,
  { onData, onActivity }: SseReadOptions
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) return;
    onActivity?.();
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");

      for (const line of frame.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (payload) onData(payload);
      }
    }
  }
}
