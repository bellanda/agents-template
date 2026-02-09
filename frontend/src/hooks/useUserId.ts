/**
 * Hook to get current user ID.
 *
 * In this template, returns a fixed "default_user" for simplicity.
 * To integrate with real authentication, replace this hook with your auth provider:
 *
 * ```tsx
 * // Example with auth context
 * export function useUserId(): [string, () => void] {
 *   const { user } = useAuth();
 *   return [user?.id || "default_user", () => {}];
 * }
 * ```
 */
export function useUserId(): [string, () => void] {
  // Always return the same user ID for template simplicity
  // Replace this with your auth system when integrating
  return ["default_user", () => {}];
}
