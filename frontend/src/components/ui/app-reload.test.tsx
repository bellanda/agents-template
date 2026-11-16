// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { AppReloadButton } from "@/components/ui/app-reload-button";
import { usePullToRefresh } from "@/hooks/usePullToRefresh";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

// Threshold is 72px AFTER the 0.5 resistance: the finger must travel more than 144px.
const PULL_BEYOND_THRESHOLD_PX = 200;
const PULL_BELOW_THRESHOLD_PX = 40;

function mockDisplayMode(installed: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: installed && query.includes("display-mode"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

function renderWithQueryClient(ui: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// jsdom has no Touch/TouchEvent; the handler only reads `touches[0].clientY`.
function dispatchTouch(node: HTMLElement, type: string, clientY: number) {
  const event = new Event(type, { bubbles: true }) as Event & { touches: { clientY: number }[] };
  event.touches = [{ clientY }];
  node.dispatchEvent(event);
}

function PullProbe({ onRefresh }: { onRefresh: () => void }) {
  const { scrollRef } = usePullToRefresh(onRefresh);
  return <main ref={scrollRef} />;
}

async function pullBy(distance: number) {
  const scroller = screen.getByRole("main");
  act(() => dispatchTouch(scroller, "touchstart", 0));
  act(() => dispatchTouch(scroller, "touchmove", distance));
  await act(async () => dispatchTouch(scroller, "touchend", distance));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AppReloadButton", () => {
  it("shows when installed, where there is no F5", () => {
    mockDisplayMode(true);
    renderWithQueryClient(<AppReloadButton />);
    expect(screen.getByRole("button", { name: "Recarregar" })).toBeDefined();
  });

  it("hides in the browser, where F5 already works", () => {
    mockDisplayMode(false);
    renderWithQueryClient(<AppReloadButton />);
    expect(screen.queryByRole("button", { name: "Recarregar" })).toBeNull();
  });
});

describe("usePullToRefresh", () => {
  it("refreshes when the pull passes the threshold", async () => {
    const onRefresh = vi.fn();
    render(<PullProbe onRefresh={onRefresh} />);
    await pullBy(PULL_BEYOND_THRESHOLD_PX);
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));
  });

  it("ignores a short pull", async () => {
    const onRefresh = vi.fn();
    render(<PullProbe onRefresh={onRefresh} />);
    await pullBy(PULL_BELOW_THRESHOLD_PX);
    expect(onRefresh).not.toHaveBeenCalled();
  });
});
