/**
 * Reference: components/layouts/sidebar-layout.tsx (from the reference frontend).
 *
 * SidebarProvider + SidebarInset shell. Header = trigger + separator +
 * breadcrumb derived from the pathname. The `/app` layout route's component is
 * just <SidebarLayout><Outlet /></SidebarLayout>.
 */

import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { Fragment, type ReactNode } from "react";

import { AppSidebar } from "@/components/sidebar/app-sidebar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

const SEGMENT_LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  catalog: "Catalog",
  lineage: "Lineage",
  admin: "Admin",
  users: "Users",
  "owned-domains": "My domains",
  table: "Table",
};

/** Path segments after the `/app` shell prefix, mapped to human labels. */
function crumbLabelsFromPath(pathname: string): string[] {
  const segments = pathname.split("/").filter(Boolean).slice(1);
  return segments.map((segment) => SEGMENT_LABELS[segment] ?? decodeURIComponent(segment));
}

interface SidebarLayoutProps {
  children?: ReactNode;
}

export function SidebarLayout({ children }: SidebarLayoutProps) {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const crumbs = crumbLabelsFromPath(pathname);

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link to="/app/dashboard">App</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              {crumbs.map((label, index) => (
                <Fragment key={`${label}-${index}`}>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    {index === crumbs.length - 1 ? (
                      <BreadcrumbPage>{label}</BreadcrumbPage>
                    ) : (
                      label
                    )}
                  </BreadcrumbItem>
                </Fragment>
              ))}
            </BreadcrumbList>
          </Breadcrumb>
        </header>
        <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-4">
          {children ?? <Outlet />}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
