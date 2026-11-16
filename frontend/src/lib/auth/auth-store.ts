/**
 * Global auth store, readable OUTSIDE React (route `beforeLoad`, services). Ported from the
 * fleet's canonical store (audit 2026-11-13 template-gap-03), with the user type left generic
 * because the template ships no login: the app picks `TUser` when it wires its own auth.
 *
 * `ready` resolves exactly once, when the bootstrap (session refresh -> "who am I") settles.
 * Gate `RouterProvider` on it so every `beforeLoad` reads `getState()` synchronously, with no
 * polling and no network inside the router (the deadline-based variant redirected authenticated
 * users to /login on slow mobile connections).
 *
 * SECURITY: client-side only, manipulable via DevTools. This is UX (route guarding), never
 * authorization - the backend validates every request.
 */
export type AuthStatus = "pending" | "authenticated" | "anonymous";

export class AuthStore<TUser = unknown> {
  private user: TUser | null = null;
  private status: AuthStatus = "pending";
  private listeners = new Set<() => void>();
  private markReady: () => void = () => {};
  private refetch: (() => Promise<void>) | null = null;

  readonly ready: Promise<void>;

  constructor() {
    this.ready = new Promise<void>((resolve) => {
      this.markReady = resolve;
    });
  }

  getState() {
    return {
      user: this.user,
      isAuthenticated: this.status === "authenticated",
      isLoading: this.status === "pending",
      status: this.status,
    };
  }

  setState(state: { user: TUser | null; isAuthenticated: boolean; isLoading: boolean }) {
    this.user = state.user;
    this.status = state.isLoading
      ? "pending"
      : state.isAuthenticated
        ? "authenticated"
        : "anonymous";
    // Idempotent: resolving an already-settled promise is a no-op.
    if (this.status !== "pending") this.markReady();
    this.listeners.forEach((listener) => listener());
  }

  /** The provider owns the network call; the store only exposes it to callers outside React. */
  registerRefetch(refetch: () => Promise<void>) {
    this.refetch = refetch;
  }

  /** Re-hydrate `user`. Never flips back to "pending": that makes route guards treat an
   * authenticated user as logged out mid-navigation. */
  async refetchUser(): Promise<void> {
    await this.refetch?.();
  }

  subscribe(listener: () => void) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  reset() {
    this.setState({ user: null, isAuthenticated: false, isLoading: false });
  }
}

export const authStore = new AuthStore();
