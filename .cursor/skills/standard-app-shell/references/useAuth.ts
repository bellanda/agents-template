/**
 * Reference: the `useAuth()` composition hook (from the reference frontend).
 *
 * Composition hook over the zustand `useAuthStore` — the single public API for
 * auth inside React. NOT a Context: components subscribe to the store directly,
 * so there is no provider and no re-render storm.
 *
 * Tokens live in the store because `beforeLoad` (runs outside React) and the
 * ApiClient need synchronous access — those read `useAuthStore.getState()`
 * directly, never this hook.
 */

import { useLogin } from "@/api/auth";
import { useAuthStore } from "@/stores/auth";

export function useAuth() {
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const clear = useAuthStore((s) => s.clear);
  const login = useLogin();

  return {
    user,
    isAuthenticated: !!accessToken,
    login,
    logout: clear,
  };
}

/**
 * Companion store — src/stores/auth.ts. Tokens + a minimal user snapshot,
 * persisted to localStorage. `beforeLoad` reads `useAuthStore.getState()`.
 *
 *   interface AuthState {
 *     accessToken: string | null;
 *     refreshToken: string | null;
 *     user: AuthUser | null;
 *     setSession: (s: { accessToken; refreshToken; user }) => void;
 *     clear: () => void;
 *   }
 *
 *   export const useAuthStore = create<AuthState>()(
 *     persist((set) => ({ ... }), { name: "<app>-auth" })
 *   );
 */
