// Canonical named layouts for an authenticated app shell.
//
// The macro UI/UX lives HERE, in one place per layout — never spread across pages.
// A page NEVER sets its own max-w; the layout owns width and framing.
//
//   SidebarLayout      → content capped at max-w-[1440px], centered, fluid gutter (the default)
//   SidebarChatLayout  → same sidebar + header, but content is FULL-BLEED (chat / WhatsApp)
//
// Both share one internal `SidebarShell` (provider + sidebar + header, defined once). The only
// difference is how the content region is wrapped — that is the entire point of named layouts.
//
// The decision of WHICH route uses WHICH layout lives in ONE place (the layout-route, e.g.
// `_authenticated.tsx`), as a constant:
//
//   const CHAT_LAYOUT_PREFIXES = ["/chat"] as const;
//   const useChatLayout = CHAT_LAYOUT_PREFIXES.some((p) => pathname.startsWith(p));
//   return useChatLayout ? <SidebarChatLayout /> : <SidebarLayout />;
//
// (TanStack pathless layout routes are an equally valid, more idiomatic option — use them if the
// project already nests routes that way.)

import { AppSidebar } from "@/components/sidebar/app-sidebar";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { usePageHeader } from "@/contexts/PageHeaderContext";
import { Outlet } from "@tanstack/react-router";
import type { ReactNode } from "react";

// Single source of truth for the app content width. The cap is a brake for 2K/4K — on a 1920
// screen at 125% scaling the CSS viewport is 1536, so the shell is already FLUID there and the
// cap never engages. What the reader actually feels at that size is the gutter, so the gutter is
// fluid too instead of a 16px/24px step: it grows with the viewport and stops at 32px.
const CONTENT_MAX_W = "max-w-[1440px]";
const CONTENT_PX = "px-[clamp(1rem,2vw,2rem)]";

interface SidebarLayoutProps {
  children?: ReactNode;
}

// Internal shell: SidebarProvider + AppSidebar + header. Defined ONCE; both layouts compose it.
// `fullBleed` makes the header span the full width too — so it lines up with full-bleed content
// (chat). Without it the title/actions float in a centered 1440 box while the chat fills the screen.
function SidebarShell({
  children,
  fullBleed = false,
}: {
  children: ReactNode;
  fullBleed?: boolean;
}) {
  const { title, subtitle, actions } = usePageHeader();

  // The header uses the SAME width cap and the SAME fluid gutter as the content — otherwise the
  // title sits on a different left edge than the page below it, and the misalignment is visible
  // at every viewport where the clamp is not at one of its ends.
  const headerInner = fullBleed
    ? `flex w-full items-center justify-between ${CONTENT_PX}`
    : `mx-auto flex w-full ${CONTENT_MAX_W} items-center justify-between ${CONTENT_PX}`;

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
          <div className={headerInner}>
            <div className="flex flex-1 items-center gap-3">
              <SidebarTrigger className="-ml-1" />
              <Separator orientation="vertical" className="mr-2 h-4" />
              <div className="flex flex-col gap-0.5">
                {title && (
                  <h1 className="text-base leading-none font-bold tracking-tight">{title}</h1>
                )}
                {subtitle && (
                  <p className="text-muted-foreground text-xs leading-none">{subtitle}</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-4">
              {actions && <div className="flex items-center gap-2">{actions}</div>}
              <ThemeToggle />
            </div>
          </div>
        </header>
        <main className="flex min-h-0 flex-1 flex-col overflow-y-auto">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}

// Default layout: content centered and capped at 1440. Every normal page uses this.
export function SidebarLayout({ children }: SidebarLayoutProps) {
  return (
    <SidebarShell>
      <div className={`mx-auto w-full ${CONTENT_MAX_W} ${CONTENT_PX} py-4 md:py-6`}>
        {children || <Outlet />}
      </div>
    </SidebarShell>
  );
}

// Full-bleed layout: sidebar + header stay (no auto-collapse), content fills the area.
// The page content must use `flex-1 min-h-0` to fill — NEVER `h-[calc(100dvh-Xrem)]`.
// `fullBleed` also un-caps the header so it tracks the content edge-to-edge.
export function SidebarChatLayout({ children }: SidebarLayoutProps) {
  return <SidebarShell fullBleed>{children || <Outlet />}</SidebarShell>;
}
