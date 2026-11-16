import { describe, expect, it, vi } from "vitest";
import { AuthStore } from "./auth-store";

// template-gap-03: route guards read the store synchronously after `ready`.
describe("AuthStore", () => {
  it("starts pending, resolves `ready` once settled, and notifies subscribers", async () => {
    const store = new AuthStore<{ id: number }>();
    const listener = vi.fn();
    store.subscribe(listener);
    expect(store.getState()).toMatchObject({ status: "pending", isLoading: true });

    store.setState({ user: { id: 1 }, isAuthenticated: true, isLoading: false });
    await store.ready;

    expect(store.getState()).toMatchObject({ status: "authenticated", user: { id: 1 } });
    expect(listener).toHaveBeenCalledTimes(1);

    store.reset();
    expect(store.getState()).toMatchObject({ status: "anonymous", user: null });
  });

  it("refetchUser delegates to the registered refetch and never goes back to pending", async () => {
    const store = new AuthStore();
    const refetch = vi.fn(async () => {});
    store.registerRefetch(refetch);
    store.setState({ user: null, isAuthenticated: false, isLoading: false });

    await store.refetchUser();

    expect(refetch).toHaveBeenCalledTimes(1);
    expect(store.getState().status).toBe("anonymous");
  });
});
