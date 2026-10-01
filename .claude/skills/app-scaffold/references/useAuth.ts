/**
 * Reference: shape of the real `useAuth()` (kailos `frontend/src/hooks/useAuth.ts`, mirrored in
 * promoservice/akmeo/balizap). Copy the real file from kailos — this stub only documents the contract.
 *
 * Corrected 2026-10-01: there is NO zustand `useAuthStore`. Auth state is:
 *   - `lib/api/access-token-store.ts`  access token in memory (+ BroadcastChannel across tabs)
 *   - `lib/auth/auth-store.ts`         vanilla `authStore` (`getState()`, `subscribe`, `ready`);
 *                                      main.tsx awaits `authStore.ready` before mounting the router
 *   - `lib/api/context.tsx`            `useDataProvider()` → { auth, user, isAuthenticated, isLoading }
 *
 * `beforeLoad` (outside React) reads `authStore.getState()`, never this hook.
 */

import { setAccessToken } from "@/lib/api/access-token-store";
import { useDataProvider } from "@/lib/api/context";
import type { LoginCredentials } from "@/lib/api/types";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function useAuth() {
  const { auth, user, isAuthenticated, isLoading } = useDataProvider();
  const queryClient = useQueryClient();

  const login = useMutation({
    mutationFn: async (credentials: LoginCredentials) => {
      // Login starts from zero: old token, previous account's cache and the server-side refresh
      // family must die BEFORE the new session is minted.
      setAccessToken(null);
      queryClient.clear();
      await auth.endServerSession();
      return auth.login(credentials);
    },
  });

  return { user, isAuthenticated, isLoading, login /* , logout, can helpers … see kailos */ };
}
