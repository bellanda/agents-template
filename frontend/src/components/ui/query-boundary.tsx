import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import type { ReactNode } from "react";

/** Subset of a TanStack `UseQueryResult` that the boundary needs (any query result fits). */
interface BoundaryQuery<TData> {
  data: TData | undefined;
  error: unknown;
  isError: boolean;
  refetch: () => unknown;
}

interface QueryBoundaryProps<TData> {
  query: BoundaryQuery<TData>;
  /** Detail/section title for the failure ("Não foi possível carregar a conta"). */
  errorTitle?: string;
  /** Shown on a 404 (stale link, deleted record); a retry would never help, so there is none. */
  notFoundTitle?: string;
  /** Pending state. Default is a neutral skeleton; pass the screen's own spinner/skeleton. */
  loading?: ReactNode;
  className?: string;
  children: (data: TData) => ReactNode;
}

function isNotFound(error: unknown): boolean {
  return (
    typeof error === "object" && error !== null && (error as { status?: unknown }).status === 404
  );
}

/**
 * Loading / error / data switch for a detail screen or dashboard section (audit 2026-11-13
 * promoservice-fe-finance-stock-05).
 *
 * Replaces `if (isLoading || !data) return <Spinner/>`: when the query FAILS, `isLoading` is false
 * but `data` is undefined, so the old shape treated the failure as "still loading" and the person
 * stared at a spinner forever with no message and no retry. Here a failure with no data to show
 * renders `ErrorState` ("Tentar novamente" → `refetch`), a 404 renders a not-found message, and
 * only a genuinely pending query shows `loading`. A background refetch failure keeps showing the
 * stale data (the global query toast already tells the user).
 *
 *   <QueryBoundary query={accountQuery} errorTitle="Não foi possível carregar a conta">
 *     {(account) => <AccountBody account={account} />}
 *   </QueryBoundary>
 *
 * Screens that cannot wrap their JSX (hooks after the early return) use the same shape inline:
 * `if (query.isError && !query.data) return <ErrorState error={query.error} onRetry={() => query.refetch()} />`.
 */
export function QueryBoundary<TData>({
  query,
  errorTitle,
  notFoundTitle = "Não encontrado",
  loading,
  className,
  children,
}: QueryBoundaryProps<TData>) {
  if (query.data !== undefined && query.data !== null) return <>{children(query.data)}</>;
  if (query.isError) {
    if (isNotFound(query.error)) {
      return <ErrorState error={query.error} title={notFoundTitle} className={className} />;
    }
    return (
      <ErrorState
        error={query.error}
        title={errorTitle}
        onRetry={() => void query.refetch()}
        className={className}
      />
    );
  }
  return <>{loading ?? <Skeleton className="h-40 w-full" />}</>;
}
