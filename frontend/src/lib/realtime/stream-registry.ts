/**
 * Event registry for the ONE per-user SSE stream of an app (fleet standard, audit 2026-11-13
 * core-spa-05/09). The hook that owns the connection calls `dispatchStreamEvent` for every frame
 * and `runResync` after a reopen; features plug in WITHOUT touching the hook:
 *   1. Add the event type to `AppStreamEvent` below (discriminated union on `type`).
 *   2. In a module of its own, call `registerStreamHandler(type, (event, ctx) => ...)` and, for
 *      what must be refetched after a reconnect / burst `batch` frame, `registerResync(...)`.
 *   3. Import that module once from the stream hook (registration is an import side effect).
 * Handlers are additive; a throwing handler never breaks the others or the stream.
 *
 * Built-in frames: `batch` (server-side burst guard, the backend `FrameLimiter`: "many changes,
 * refetch once") runs the resync handlers; `entity.changed` is mapped to query invalidation by
 * `entity-changed.ts`.
 */
import type { QueryClient } from "@tanstack/react-query";

/** Server-side burst guard (backend `FrameLimiter`): "many changes happened, refetch once". */
export interface StreamBatchEvent {
  type: "batch";
  payload: { reason: string };
}

/** Something another user / a webhook / a routine changed. Content never travels: refetch. */
export interface EntityChangedEvent {
  type: "entity.changed";
  payload: { entity: string; orgId: string; ids?: string[] };
}

export type AppStreamEvent = StreamBatchEvent | EntityChangedEvent;

export interface StreamContext {
  queryClient: QueryClient;
}

type EventOfType<T extends AppStreamEvent["type"]> = Extract<AppStreamEvent, { type: T }>;
type StreamHandler<T extends AppStreamEvent["type"]> = (
  event: EventOfType<T>,
  ctx: StreamContext
) => void;
type ResyncHandler = (ctx: StreamContext) => void;

// Stored type-erased: the public `registerStreamHandler` signature is what keeps call sites typed.
const handlersByType = new Map<string, Array<(event: never, ctx: StreamContext) => void>>();
const resyncHandlers = new Set<ResyncHandler>();

export function registerStreamHandler<T extends AppStreamEvent["type"]>(
  type: T,
  handler: StreamHandler<T>
): () => void {
  const list = handlersByType.get(type) ?? [];
  list.push(handler as (event: never, ctx: StreamContext) => void);
  handlersByType.set(type, list);
  return () => {
    handlersByType.set(
      type,
      (handlersByType.get(type) ?? []).filter((h) => h !== (handler as unknown))
    );
  };
}

/** What to refetch after a reconnect (no replay on the server) or a `batch` frame. */
export function registerResync(handler: ResyncHandler): () => void {
  resyncHandlers.add(handler);
  return () => resyncHandlers.delete(handler);
}

function runSafely(run: () => void) {
  try {
    run();
  } catch {
    // One broken handler must not starve the others or kill the stream loop.
  }
}

export function runResync(ctx: StreamContext) {
  for (const handler of resyncHandlers) runSafely(() => handler(ctx));
}

export function dispatchStreamEvent(event: AppStreamEvent, ctx: StreamContext) {
  if (event.type === "batch") {
    runResync(ctx);
    return;
  }
  for (const handler of handlersByType.get(event.type) ?? []) {
    runSafely(() => handler(event as never, ctx));
  }
}
