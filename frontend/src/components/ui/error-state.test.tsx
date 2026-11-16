// @vitest-environment jsdom
import { ErrorState } from "@/components/ui/error-state";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

// SHARED WIDGET test (byte-identical fleet-wide). Locks the contract every caller relies on:
// a failed load is an alert with a retry, never an empty list.
describe("ErrorState", () => {
  it("renders an alert with the default title and a retry that calls onRetry", () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new Error("boom")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Não foi possível carregar esta lista")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("hides the retry button when onRetry is not given", () => {
    render(<ErrorState error={new Error("boom")} title="Falhou" />);
    expect(screen.getByText("Falhou")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("prefers an explicit description and omits the detail line when there is no error", () => {
    const { rerender } = render(<ErrorState description="Sem rede agora" error={new Error("x")} />);
    expect(screen.getByText("Sem rede agora")).toBeTruthy();
    rerender(<ErrorState title="Falhou" />);
    expect(screen.queryByText("Sem rede agora")).toBeNull();
    expect(screen.getAllByRole("alert")[0].querySelectorAll("p")).toHaveLength(1);
  });

  it("uses tighter vertical padding in compact size", () => {
    render(<ErrorState size="compact" description="x" />);
    expect(screen.getByRole("alert").className).toContain("py-8");
  });
});
