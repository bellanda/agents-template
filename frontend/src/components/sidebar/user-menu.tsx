import { InstallAppMenuItem } from "@/components/pwa/InstallAppButton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarMenuButton } from "@/components/ui/sidebar";
import { CaretUpIcon } from "@phosphor-icons/react";

/**
 * User menu in the sidebar footer (audit 2026-11-13 template-gap-05). It exists so the PWA
 * contract has its home: "Instalar app" lives ONLY here (never on login/landing), see
 * `pwa-mobile.md`. An app with real auth adds its own items (profile, logout) in the content;
 * `InstallInstructionsDialog` is rendered once by `SidebarLayout`, outside the dropdown.
 */
export function UserMenu({ name, email }: { name: string; email: string }) {
  const initials = name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton className="h-10 items-center gap-2 rounded-none px-2">
          <div className="bg-muted flex size-7 items-center justify-center rounded-full text-xs font-medium">
            {initials}
          </div>
          <div className="flex flex-1 flex-col text-left leading-tight">
            <span className="truncate text-xs font-medium">{name}</span>
            <span className="text-muted-foreground truncate text-[0.625rem]">{email}</span>
          </div>
          <CaretUpIcon className="ml-auto size-4" />
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="min-w-56">
        <InstallAppMenuItem />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
