import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AdminPermission } from "@/types/admin";
import { useMemo } from "react";
import { groupPermissions } from "./groupPermissions";
import { verbMeta } from "./permissionVerbs";

interface PermissionGroupListProps {
  /** Permission keys to display. */
  permissions: string[];
  /** Full catalog — provides pt/group/groupPt/order per key. */
  catalog: AdminPermission[];
  /** Keys granted only via explicit override (renders a marker on the badge). */
  overrideKeys?: Set<string>;
  emptyText?: string;
}

/** Grouped, line-by-line permission display (skill frontend, ref permissions-display.md):
 * one row per domain group (header + count), badges colored/iconed by the CRUD verb in
 * canonical order. Replaces the flat badge cloud. */
export function PermissionGroupList({
  permissions,
  catalog,
  overrideKeys,
  emptyText,
}: PermissionGroupListProps) {
  const groups = useMemo(() => groupPermissions(permissions, catalog), [permissions, catalog]);

  if (groups.length === 0) {
    return (
      <div className="text-muted-foreground rounded-md border border-dashed p-4 text-center text-xs">
        {emptyText ?? "Nenhuma permissão."}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {groups.map((g) => (
        <div key={g.group} className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{g.groupPt}</span>
            <span className="text-muted-foreground text-xs">({g.items.length})</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {g.items.map((item) => {
              const meta = verbMeta(item.permission);
              const Icon = meta.icon;
              return (
                <Badge
                  key={item.permission}
                  variant="outline"
                  className={cn("gap-1 font-normal", meta.badgeClass)}
                  title={item.permission}
                >
                  <Icon className="h-3 w-3" />
                  {item.pt}
                  {overrideKeys?.has(item.permission) ? (
                    <span className="ml-0.5 text-[10px] opacity-70">• override</span>
                  ) : null}
                </Badge>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
