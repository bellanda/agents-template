// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  INVALIDATION_WINDOW_MS,
  registerEntityChanged,
  registerEntityQueries,
} from "../entity-changed";
import { dispatchStreamEvent } from "../stream-registry";

function entityEvent(entity: string, orgId = "org-1") {
  return { type: "entity.changed", payload: { entity, orgId } } as const;
}

describe("entity.changed", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("invalidates the registered key prefixes, ignores unknown entities, coalesces bursts", () => {
    const queryClient = new QueryClient();
    const spy = vi.spyOn(queryClient, "invalidateQueries");
    registerEntityQueries("widget", ({ orgId }) => [[`/orgs/${orgId}/widgets`]]);
    const ctx = { queryClient };

    dispatchStreamEvent(entityEvent("nobody-registered"), ctx);
    expect(spy).not.toHaveBeenCalled();

    // 50 events in a burst: one at once (leading) + ONE trailing, not 50 refetches.
    for (let i = 0; i < 50; i += 1) dispatchStreamEvent(entityEvent("widget"), ctx);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith({ queryKey: ["/orgs/org-1/widgets"] });
    vi.advanceTimersByTime(INVALIDATION_WINDOW_MS);
    expect(spy).toHaveBeenCalledTimes(2);
    vi.advanceTimersByTime(INVALIDATION_WINDOW_MS * 2);
    expect(spy).toHaveBeenCalledTimes(2);

    // Window closed: the next event is leading again.
    dispatchStreamEvent(entityEvent("widget"), ctx);
    expect(spy).toHaveBeenCalledTimes(3);
  });

  // audit 2026-11-15 r2-nexarena-fe-01: the trailing run used to replay the FIRST event's ids.
  it("hands the trailing run the union of the ids seen in the window, undefined when any had none", () => {
    const queryClient = new QueryClient();
    const seen: (string[] | undefined)[] = [];
    registerEntityChanged("gadget", ({ ids }) => void seen.push(ids));
    const ctx = { queryClient };
    const withIds = (ids?: string[]) =>
      ({ type: "entity.changed", payload: { entity: "gadget", orgId: "org-1", ids } }) as const;

    dispatchStreamEvent(withIds(["A"]), ctx);
    dispatchStreamEvent(withIds(["B"]), ctx);
    dispatchStreamEvent(withIds(["C", "A"]), ctx);
    expect(seen).toEqual([["A"]]);
    vi.advanceTimersByTime(INVALIDATION_WINDOW_MS);
    expect(seen).toHaveLength(2);
    expect([...(seen[1] ?? [])].sort()).toEqual(["B", "C", "A"].sort());

    // An event without ids makes the whole window "anything may have changed".
    vi.advanceTimersByTime(INVALIDATION_WINDOW_MS * 3);
    seen.length = 0;
    dispatchStreamEvent(withIds(["A"]), ctx);
    dispatchStreamEvent(withIds(), ctx);
    dispatchStreamEvent(withIds(["B"]), ctx);
    vi.advanceTimersByTime(INVALIDATION_WINDOW_MS);
    expect(seen).toEqual([["A"], undefined]);
  });
});
