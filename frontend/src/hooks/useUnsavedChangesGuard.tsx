import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useBlocker } from "@tanstack/react-router";
import { useEffect, useRef, type ReactNode, type RefObject } from "react";

interface UnsavedChangesGuardOptions {
  /** True while the screen holds edits that are not saved (the same flag as `DirtyBottomBar.visible`). */
  when: boolean;
  /**
   * Runs right before the navigation proceeds after the person chose to leave. Put the cleanup of
   * anything the draft created on the server here (e.g. TV sounds uploaded in this session).
   */
  onLeave?: () => void;
  /**
   * Search keys that may change without leaving the screen (the wizard step lives in the URL).
   * Everything else, including the path and the settings hub's `?settings=`, counts as leaving.
   */
  ignoreSearchKeys?: readonly string[];
  /**
   * While `bypass.current` is true nothing is blocked. Set it right BEFORE a navigation that the
   * screen itself triggers after saving (onboarding `onSaved` advances the step): `when` is read
   * from the last render, which still says "dirty" at that instant, so without this the person
   * would be asked to discard what they just saved.
   */
  bypass?: RefObject<boolean>;
  title?: string;
  description?: string;
}

/**
 * Blocks IN-APP navigation (closing the settings hub, switching section, another route, browser
 * Back) while a draft is dirty and asks first with the fleet `ConfirmDialog` (audit 2026-11-13
 * kailos-fe-dashboard-tv-insights-06). `beforeunload` only covers F5/closing the tab, so the draft
 * of a long wizard vanished silently on a stray click outside the dialog or Esc.
 *
 * Returns the dialog node: render it once next to the screen's save bar.
 *
 *   const guard = useUnsavedChangesGuard({ when: isDirty, onLeave: discardDraft, ignoreSearchKeys: ["tvStep"] });
 *   return <>{...}{guard}</>;
 */
export function useUnsavedChangesGuard({
  when,
  onLeave,
  ignoreSearchKeys = [],
  bypass,
  title = "Descartar alterações não salvas?",
  description = "Você tem alterações que ainda não foram salvas. Se sair agora, elas serão perdidas.",
}: UnsavedChangesGuardOptions): ReactNode {
  const blocker = useBlocker({
    disabled: !when,
    // `withResolver` keeps the navigation pending until the dialog answers; the browser-level
    // prompt stays with the screen's own `beforeunload` listener (F5 / closing the tab).
    withResolver: true,
    enableBeforeUnload: false,
    shouldBlockFn: ({ current, next }) => {
      if (bypass?.current) return false;
      if (current.pathname !== next.pathname) return true;
      const ignored = new Set(ignoreSearchKeys);
      const relevant = (search: Record<string, unknown>) =>
        JSON.stringify(
          Object.entries(search)
            .filter(([key]) => !ignored.has(key))
            .sort()
        );
      return (
        relevant(current.search as Record<string, unknown>) !==
        relevant(next.search as Record<string, unknown>)
      );
    },
  });

  return (
    <ConfirmDialog
      open={blocker.status === "blocked"}
      onOpenChange={(open) => {
        if (!open) blocker.reset?.();
      }}
      title={title}
      description={description}
      confirmLabel="Descartar e sair"
      cancelLabel="Continuar editando"
      destructive
      onConfirm={() => {
        onLeave?.();
        blocker.proceed?.();
      }}
    />
  );
}

/**
 * `bypass` ref for screens whose save handler triggers a navigation itself (onboarding `onSaved`
 * advances `?tab=`): set `.current = true` right before `onSaved()`. Cleared once the draft is
 * clean again (audit 2026-11-13 carry-fe review: the guard otherwise asked to discard a just-saved draft).
 */
export function useSavedBypass(isDirty: boolean): RefObject<boolean> {
  const ref = useRef(false);
  useEffect(() => {
    if (!isDirty) ref.current = false;
  }, [isDirty]);
  return ref;
}
