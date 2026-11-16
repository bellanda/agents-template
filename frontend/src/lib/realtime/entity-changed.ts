/**
 * `entity.changed` -> query invalidation (fleet standard, audit 2026-11-13 core-spa-05).
 *
 * The backend emits `{type: "entity.changed", payload: {entity, org_id, ids?}}` on the per-user
 * channel, AFTER COMMIT, for entities other users look at (an approval raised by a seller, a kit
 * handed out by another operator). The bell is a notification, not an invalidation: this is what
 * keeps the lists behind it fresh without F5.
 *
 * An app maps each entity name to its queries, once, in a module imported by the stream hook:
 *   - app with `lib/api/invalidation.ts` (entity graph):
 *       registerEntityChanged("approval", ({ orgId }, { queryClient }) =>
 *         invalidateEntity(queryClient, orgId, "approval"));
 *   - plain endpoint-prefix keys (TanStack matches by prefix, so `[endpoint]` refreshes every
 *     variant: pending / history / counters):
 *       registerEntityQueries("approval", ({ orgId }) => [[approvalsEndpoint(orgId)]]);
 * Unknown entities are ignored. Handlers run COALESCED per (entity, org): `invalidateQueries`
 * cancels and restarts an in-flight fetch, so a burst of events would otherwise be a burst of
 * requests (core-spa-09). The first event goes out at once, the rest of the window becomes ONE
 * trailing run.
 *
 * `ids` is a HINT and lossy end to end (audit 2026-11-15 r2-nexarena-fe-01): the server limiter
 * keeps one frame per (entity, org) per second and the client coalesces too. The trailing run
 * therefore receives the UNION of the ids seen in its window, and `ids` is undefined when any
 * merged event carried none (or the server dropped them): a handler MUST read "no ids" as
 * "anything of this entity may have changed" and invalidate broadly, never return early.
 */
import type { QueryClient, QueryKey } from "@tanstack/react-query";
import { registerStreamHandler, type StreamContext } from "./stream-registry";

export const INVALIDATION_WINDOW_MS = 1_000;

interface WindowState {
  timer: ReturnType<typeof setTimeout> | null;
  pending: boolean;
}
const stateByClient = new WeakMap<QueryClient, Map<string, WindowState>>();

/** Leading + trailing throttle keyed by `id`: N calls inside the window cost two `run`s at most. */
export function coalesce(
  queryClient: QueryClient,
  id: string,
  run: () => void,
  windowMs: number = INVALIDATION_WINDOW_MS
): void {
  const states = stateByClient.get(queryClient) ?? new Map<string, WindowState>();
  stateByClient.set(queryClient, states);
  const existing = states.get(id);
  if (existing) {
    existing.pending = true;
    return;
  }
  const state: WindowState = { timer: null, pending: false };
  states.set(id, state);
  run();
  const close = () => {
    if (state.pending) {
      state.pending = false;
      run();
      state.timer = setTimeout(close, windowMs);
      return;
    }
    states.delete(id);
  };
  state.timer = setTimeout(close, windowMs);
}

/** Coalesced `invalidateQueries` for one key prefix (for stream handlers that fire per event). */
export function coalescedInvalidate(
  queryClient: QueryClient,
  queryKey: QueryKey,
  windowMs: number = INVALIDATION_WINDOW_MS
): void {
  coalesce(
    queryClient,
    `key:${JSON.stringify(queryKey)}`,
    () => void queryClient.invalidateQueries({ queryKey }),
    windowMs
  );
}

export interface EntityChange {
  orgId: string;
  /** Undefined/empty = unknown: treat the whole entity (every list and detail) as stale. */
  ids?: string[];
}
type EntityHandler = (change: EntityChange, ctx: StreamContext) => void;

const handlersByEntity = new Map<string, EntityHandler>();

export function registerEntityChanged(entity: string, handler: EntityHandler): void {
  handlersByEntity.set(entity, handler);
}

/** Sugar for the common case: the entity owns these query-key prefixes. */
export function registerEntityQueries(
  entity: string,
  queries: (change: EntityChange) => readonly QueryKey[]
): void {
  registerEntityChanged(entity, (change, { queryClient }) => {
    for (const queryKey of queries(change)) void queryClient.invalidateQueries({ queryKey });
  });
}

/** Ids accumulated per coalescing key since the last run; `null` = some event had no ids. */
const pendingIdsByClient = new WeakMap<QueryClient, Map<string, Set<string> | null>>();

registerStreamHandler("entity.changed", (event, ctx) => {
  const { entity, orgId, ids } = event.payload;
  const handler = handlersByEntity.get(entity);
  if (!handler) return;
  const key = `entity:${entity}:${orgId}`;
  const pendingByKey = pendingIdsByClient.get(ctx.queryClient) ?? new Map();
  pendingIdsByClient.set(ctx.queryClient, pendingByKey);
  const pending = pendingByKey.get(key);
  if (!ids || ids.length === 0 || pending === null) pendingByKey.set(key, null);
  else pendingByKey.set(key, new Set([...(pending ?? []), ...ids]));
  coalesce(ctx.queryClient, key, () => {
    // Runs now (leading) or at the window end (trailing): hands over everything accumulated.
    const merged = pendingByKey.get(key);
    pendingByKey.delete(key);
    handler({ orgId, ids: merged ? [...merged] : undefined }, ctx);
  });
});
