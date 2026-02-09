import { Outlet, createRootRoute } from "@tanstack/react-router";

import { ThemeProvider } from "@/components/theme";

export const Route = createRootRoute({
  component: RootComponent
});

function RootComponent() {
  return (
    <ThemeProvider defaultTheme="dark">
      <Outlet />
    </ThemeProvider>
  );
}
