import { Outlet, createRootRoute } from "@tanstack/react-router";
import { QueryClientProvider } from "@tanstack/react-query";

import { UpdateBanner } from "@/components/app-version/UpdateBanner";
import { ThemeProvider } from "@/components/theme";
import { Toaster } from "@/components/ui/sonner";
import { createAppQueryClient } from "@/lib/api/query-client";
import { useAppVersionWatcher } from "@/lib/app-version/use-app-version-watcher";

const queryClient = createAppQueryClient();

export const Route = createRootRoute({
  component: RootComponent,
});

function RootComponent() {
  // Monta UMA vez: detecta deploy novo e troca o bundle (lib/app-version).
  const { updatePending, secondsLeft, reloadNow } = useAppVersionWatcher();
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="dark">
        <Outlet />
        <Toaster />
        {updatePending && <UpdateBanner secondsLeft={secondsLeft} onUpdate={reloadNow} />}
      </ThemeProvider>
    </QueryClientProvider>
  );
}
