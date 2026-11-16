// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const platform = vi.hoisted(() => ({ ios: true }));
vi.mock("@/lib/pwa/platform", () => ({ isIosDevice: () => platform.ios }));
vi.mock("@/hooks/useIsStandalone", () => ({ useIsStandalone: () => false }));
vi.mock("@/components/ui/sidebar", () => ({
  SidebarMenuButton: ({ children, ...props }: React.ComponentProps<"button">) => (
    <button {...props}>{children}</button>
  ),
}));

const { UserMenu } = await import("@/components/sidebar/user-menu");

afterEach(() => {
  platform.ios = true;
});

// template-gap-05: the user menu is the only home of "Instalar app".
describe("UserMenu", () => {
  it("offers 'Instalar app' inside the user menu when the app can be installed", async () => {
    render(<UserMenu name="Default User" email="d@example.com" />);
    expect(screen.queryByText("Instalar app")).toBeNull();

    fireEvent.pointerDown(screen.getByRole("button", { name: /Default User/ }), {
      button: 0,
      ctrlKey: false,
    });
    expect(await screen.findByText("Instalar app")).toBeTruthy();
  });

  it("hides the item when there is no way to install (not iOS, no native prompt)", async () => {
    platform.ios = false;
    render(<UserMenu name="Default User" email="d@example.com" />);
    fireEvent.pointerDown(screen.getByRole("button", { name: /Default User/ }), {
      button: 0,
      ctrlKey: false,
    });
    await screen.findByRole("menu");
    expect(screen.queryByText("Instalar app")).toBeNull();
  });
});
