import { Outlet, createRootRoute } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";

import { UpdateBanner } from "@/components/app-version/UpdateBanner";
import { ThemeProvider } from "@/components/theme";
import { useAppVersionWatcher } from "@/lib/app-version/use-app-version-watcher";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

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
        <Toaster position="top-right" />
        {updatePending && <UpdateBanner secondsLeft={secondsLeft} onUpdate={reloadNow} />}
      </ThemeProvider>
    </QueryClientProvider>
  );
}
