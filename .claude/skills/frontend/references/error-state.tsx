// Cross-project standard (gate frontend, ref feedback-states.md). SHARED WIDGET: byte-identical in
// every app (guarded by `src/test/__tests__/shared-widgets-drift.test.ts`, see list-screen.md).
// Change it HERE, run `python3 rules.py --shared-apply`, then `python3 rules.py` to propagate.
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api/error-message";
import { cn } from "@/lib/utils";
import { LuTriangleAlert } from "react-icons/lu";

export interface ErrorStateProps {
  /** Raw query error; becomes the description through `errorMessage`. `description` wins. */
  error?: unknown;
  /** Already-normalised message (use `errorMessage` from `lib/api/error-message`). */
  description?: string;
  /** Usually `() => query.refetch()`. Without it the retry button is hidden. */
  onRetry?: () => void;
  title?: string;
  /** `compact` for dialogs, popovers and cards; `default` for full sections. */
  size?: "default" | "compact";
  className?: string;
}

/**
 * LOAD-ERROR state, never the empty state (decision 2026-10-01, `feedback-states.md`).
 *
 * Without it, a failed query (network down, 500, 403 on a screen the front gate let through)
 * fell into `items = []` and the screen said "nothing found". The user concluded there was no data
 * and moved on; the error lived only in the console. An empty collection and a collection that
 * did not load are different facts and need different screens.
 *
 * Used by `DataList`/`StaticDataList` (via the list-hook spread), by `QueryBoundary`, and
 * standalone in any screen or section whose query can fail. The message goes through
 * `errorMessage` (one pt-BR sentence, never the browser's raw text). Extracted from
 * `data-list.tsx` on 2026-11-07 (akmeo pattern); `description`/`size`/optional `error` merged in
 * from nexarena on 2026-11-14 so the file stays identical fleet-wide.
 */
export function ErrorState({
  error,
  description,
  onRetry,
  title = "Não foi possível carregar esta lista",
  size = "default",
  className,
}: ErrorStateProps) {
  const detail = description ?? (error === undefined ? undefined : errorMessage(error));
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 px-6 text-center",
        size === "compact" ? "py-8" : "py-16",
        className
      )}
      role="alert"
    >
      <LuTriangleAlert className="text-destructive h-6 w-6" aria-hidden />
      <p className="text-sm font-medium">{title}</p>
      {detail ? <p className="text-muted-foreground max-w-prose text-xs">{detail}</p> : null}
      {onRetry && (
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          Tentar novamente
        </Button>
      )}
    </div>
  );
}
