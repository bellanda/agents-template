import { ThemeToggle } from "@/components/theme/theme-toggle";
import { Outlet } from "@tanstack/react-router";
import type { ReactNode } from "react";

interface AuthLayoutProps {
  children?: ReactNode;
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="from-background via-muted to-background relative min-h-screen bg-gradient-to-br">
      {/* Theme Toggle - Top Right Corner */}
      <div className="fixed top-4 right-4 z-50">
        <ThemeToggle />
      </div>

      {/* Main Content */}
      <main className="flex min-h-screen items-center justify-center p-4">
        <div className="w-full max-w-md">{children || <Outlet />}</div>
      </main>
    </div>
  );
}
