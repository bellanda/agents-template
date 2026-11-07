import { AppSidebar } from "@/components/sidebar/app-sidebar";
import { AppStyleWelcomeDialog, AppStylePicker } from "@/components/theme";
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
        <SidebarInset>
          <header
            data-app-header
            className="flex h-12 shrink-0 items-center gap-2 border-b px-4 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12"
          >
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" />
            <span className="text-muted-foreground text-sm font-medium">Agents Template</span>
            <div className="ml-auto flex items-center gap-2">
              <AppStylePicker />
            </div>
          </header>
          <div className="flex h-[calc(100vh-3rem)] flex-1 flex-col overflow-hidden">
            {children || <Outlet />}
          </div>
        </SidebarInset>
        {/* Só na casca de trabalho: tela operacional/kiosk/pública nunca monta este dialog. */}
        <AppStyleWelcomeDialog />
      </SidebarProvider>
    </TooltipProvider>
  );
}
