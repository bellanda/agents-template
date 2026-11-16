// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { useUnsavedChangesGuard } from "@/hooks/useUnsavedChangesGuard";
import {
  Link,
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

// The template has no global test setup, so unmount between tests by hand.
afterEach(cleanup);

// The memory routes below are not part of the app's registered route tree, so `Link` is untyped.
const AnyLink = Link as unknown as ComponentType<Record<string, unknown>>;

// Regression (audit 2026-11-13 kailos-fe-dashboard-tv-insights-06): the TV wizard draft was lost
// on any in-app exit because only `beforeunload` was guarded.
function build(opts: { dirty: boolean; onLeave?: () => void; bypass?: { current: boolean } }) {
  function Screen() {
    const guard = useUnsavedChangesGuard({
      when: opts.dirty,
      onLeave: opts.onLeave,
      ignoreSearchKeys: ["tvStep"],
      bypass: opts.bypass,
    });
    return (
      <>
        <AnyLink to="/page" search={{ settings: "tv", tvStep: "alerts" }}>
          proximo-passo
        </AnyLink>
        <AnyLink to="/page" search={{ settings: undefined, tvStep: undefined }}>
          fechar-hub
        </AnyLink>
        <AnyLink to="/other">outra-rota</AnyLink>
        {guard}
      </>
    );
  }
  const root = createRootRoute({ component: Outlet });
  const page = createRoute({
    getParentRoute: () => root,
    path: "page",
    validateSearch: (raw: Record<string, unknown>) => ({
      settings: raw.settings as string | undefined,
      tvStep: raw.tvStep as string | undefined,
    }),
    component: Screen,
  });
  const other = createRoute({
    getParentRoute: () => root,
    path: "other",
    component: () => <p>outra</p>,
  });
  return createRouter({
    routeTree: root.addChildren([page, other]),
    history: createMemoryHistory({ initialEntries: ["/page?settings=tv"] }),
  });
}

describe("useUnsavedChangesGuard", () => {
  it("asks before leaving, keeps the screen on cancel and runs onLeave on confirm", async () => {
    const onLeave = vi.fn();
    const router = build({ dirty: true, onLeave });
    render(<RouterProvider router={router} />);

    fireEvent.click(await screen.findByText("outra-rota"));
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/page");

    fireEvent.click(screen.getByRole("button", { name: "Continuar editando" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(router.state.location.pathname).toBe("/page");
    expect(onLeave).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("outra-rota"));
    fireEvent.click(await screen.findByRole("button", { name: "Descartar e sair" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/other"));
    expect(onLeave).toHaveBeenCalledTimes(1);
  });

  it("also blocks closing the settings hub (a search change), but not a wizard step change", async () => {
    const router = build({ dirty: true });
    render(<RouterProvider router={router} />);

    fireEvent.click(await screen.findByText("proximo-passo"));
    await waitFor(() => expect(router.state.location.search).toMatchObject({ tvStep: "alerts" }));
    expect(screen.queryByRole("alertdialog")).toBeNull();

    fireEvent.click(screen.getByText("fechar-hub"));
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    expect(router.state.location.search).toMatchObject({ settings: "tv" });
  });

  it("never blocks a clean screen", async () => {
    const router = build({ dirty: false });
    render(<RouterProvider router={router} />);
    fireEvent.click(await screen.findByText("outra-rota"));
    await waitFor(() => expect(router.state.location.pathname).toBe("/other"));
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  // A save that navigates on success (onboarding onSaved) must not ask to discard what was saved.
  it("does not block while the bypass flag is set", async () => {
    const router = build({ dirty: true, bypass: { current: true } });
    render(<RouterProvider router={router} />);
    fireEvent.click(await screen.findByText("outra-rota"));
    await waitFor(() => expect(router.state.location.pathname).toBe("/other"));
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });
});
