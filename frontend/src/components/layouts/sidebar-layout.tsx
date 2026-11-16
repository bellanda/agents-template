import { AppSidebar } from "@/components/sidebar/app-sidebar";
import { InstallInstructionsDialog } from "@/components/pwa/InstallAppButton";
import { AppStyleWelcomeDialog, AppStylePicker } from "@/components/theme";
import { AppReloadButton } from "@/components/ui/app-reload-button";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useAppStyleAccountSync } from "@/hooks/useAppStyle";
import { Outlet } from "@tanstack/react-router";
import type { ReactNode } from "react";

interface SidebarLayoutProps {
  children?: ReactNode;
}

export function SidebarLayout({ children }: SidebarLayoutProps) {
  useAppStyleAccountSync();
  return (
    <TooltipProvider>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset className="h-dvh min-h-0">
          <header
            data-app-header
            className="flex min-h-12 shrink-0 items-center gap-2 border-b px-4 pt-[env(safe-area-inset-top)] transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:min-h-12"
          >
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" />
            <span className="text-muted-foreground text-sm font-medium">Agents Template</span>
            <div className="ml-auto flex items-center gap-2">
              <AppReloadButton />
              <AppStylePicker />
            </div>
          </header>
          {/* flex-1 + min-h-0 inside a `h-dvh` inset (not `100vh - 3rem`): with viewport-fit=cover the
              header grows by the safe-area inset, and `vh` is the LARGE viewport on iOS. */}
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden pb-[env(safe-area-inset-bottom)]">
            {children || <Outlet />}
          </div>
        </SidebarInset>
        {/* Só na casca de trabalho: tela operacional/kiosk/pública nunca monta este dialog. */}
        <AppStyleWelcomeDialog />
        {/* Passos de "Instalar app" no iOS. O item que o abre (`InstallAppMenuItem`) mora no menu do
            usuário do app real (o template não tem auth nem esse menu): ver `pwa-mobile.md` §6. */}
        <InstallInstructionsDialog />
      </SidebarProvider>
    </TooltipProvider>
  );
}
