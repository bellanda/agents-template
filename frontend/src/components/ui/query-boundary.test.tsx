// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { QueryBoundary } from "@/components/ui/query-boundary";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

const base = { data: undefined, error: null, isError: false, refetch: vi.fn() };

// Regression for `if (isLoading || !data) return <Spinner/>`: a failed query has isLoading=false
// and data=undefined, so the old shape spun forever (audit 2026-11-13 promoservice-fe-finance-stock-05).
describe("QueryBoundary", () => {
  it("shows the loading slot only while the query is genuinely pending", () => {
    render(
      <QueryBoundary query={base} loading={<p>girando</p>}>
        {() => <p>corpo</p>}
      </QueryBoundary>
    );
    expect(screen.getByText("girando")).toBeTruthy();
    expect(screen.queryByText("corpo")).toBeNull();
  });

  it("renders ErrorState with a retry that calls refetch when the query failed", () => {
    const refetch = vi.fn();
    render(
      <QueryBoundary
        query={{ ...base, isError: true, error: new Error("boom"), refetch }}
        loading={<p>girando</p>}
        errorTitle="Não foi possível carregar a conta"
      >
        {() => <p>corpo</p>}
      </QueryBoundary>
    );
    expect(screen.queryByText("girando")).toBeNull();
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Não foi possível carregar a conta")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders a not-found message without retry on 404", () => {
    render(
      <QueryBoundary
        query={{ ...base, isError: true, error: { status: 404, message: "x" } }}
        notFoundTitle="Conta não encontrada"
      >
        {() => <p>corpo</p>}
      </QueryBoundary>
    );
    expect(screen.getByText("Conta não encontrada")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Tentar novamente" })).toBeNull();
  });

  it("keeps showing stale data when a background refetch failed", () => {
    render(
      <QueryBoundary query={{ ...base, data: { id: 1 }, isError: true, error: new Error("x") }}>
        {(data) => <p>corpo {data.id}</p>}
      </QueryBoundary>
    );
    expect(screen.getByText("corpo 1")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
