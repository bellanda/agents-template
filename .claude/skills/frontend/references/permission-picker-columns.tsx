import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { ChevronLeft, ChevronRight, Info, ShieldCheck, Users as UsersIcon } from "lucide-react";
import { groupPermissionItems } from "./groupPermissions";
import { verbMeta } from "./permissionVerbs";
import type { GrantLock, PermItem, RoleItem } from "./types";

type Direction = "add" | "remove";

function ColumnShell({
  title,
  icon,
  highlight,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  highlight?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex h-full min-h-0 flex-col gap-2 rounded-lg border p-3",
        highlight && "border-primary/20 bg-primary/5"
      )}
    >
      <div className="flex shrink-0 items-center gap-2">
        {icon}
        <span className="text-sm font-medium">{title}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto pr-2">{children}</div>
    </div>
  );
}

function DirectionChevron({ direction }: { direction: Direction }) {
  const Icon = direction === "add" ? ChevronRight : ChevronLeft;
  return <Icon className="h-4 w-4 shrink-0 opacity-40 group-hover:opacity-100" />;
}

function EmptyRow({ text }: { text: string }) {
  return <p className="text-muted-foreground py-6 text-center text-xs">{text}</p>;
}

export function RoleColumn({
  title,
  roles,
  lock,
  onToggle,
  onInfo,
  direction,
  highlight,
}: {
  title: string;
  roles: RoleItem[];
  lock: GrantLock;
  onToggle: (id: string) => void;
  onInfo: (r: RoleItem) => void;
  direction: Direction;
  highlight?: boolean;
}) {
  return (
    <ColumnShell
      title={title}
      icon={<UsersIcon className="text-muted-foreground h-4 w-4" />}
      highlight={highlight}
    >
      <div className="space-y-1">
        {roles.length === 0 ? <EmptyRow text="—" /> : null}
        {roles.map((role) => {
          const isLocked = lock.isRoleLocked(role);
          const row = (
            <div
              key={role.id}
              className={cn(
                "group flex items-center justify-between rounded-md border p-2 transition-all",
                isLocked
                  ? "bg-muted/40 cursor-not-allowed opacity-40"
                  : "hover:bg-accent cursor-pointer"
              )}
              onClick={() => !isLocked && onToggle(role.id)}
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate text-sm">{role.name}</span>
                {role.isDefault ? (
                  <Badge variant="secondary" className="h-4 px-1 text-[10px]">
                    Padrão
                  </Badge>
                ) : (
                  <Badge
                    variant="outline"
                    className="border-primary/40 text-primary h-4 px-1 text-[10px]"
                  >
                    Customizada
                  </Badge>
                )}
                {lock.isRolePrivileged(role) ? (
                  <ShieldCheck
                    className={cn(
                      "h-3 w-3 shrink-0",
                      isLocked ? "text-muted-foreground" : "text-primary"
                    )}
                  />
                ) : null}
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={(e) => {
                    e.stopPropagation();
                    onInfo(role);
                  }}
                >
                  <Info className="text-muted-foreground h-4 w-4" />
                </Button>
                <DirectionChevron direction={direction} />
              </div>
            </div>
          );
          if (isLocked) {
            return (
              <TooltipProvider key={role.id}>
                <Tooltip>
                  <TooltipTrigger asChild>{row}</TooltipTrigger>
                  <TooltipContent>
                    <p className="text-xs">{lock.roleLockMessage(role)}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            );
          }
          return row;
        })}
      </div>
    </ColumnShell>
  );
}

/**
 * Coluna de concessão de permissão. Usa o MESMO agrupamento/ordem/cor do display read-only
 * (`PermissionGroupList`) — lista chapada aqui ao lado de uma aba "Efetivas" colorida faz o usuário
 * escolher no escuro e só ver o resultado legível depois de salvar.
 */
export function PermColumn({
  title,
  perms,
  lock,
  onToggle,
  direction,
  highlight,
}: {
  title: string;
  perms: PermItem[];
  lock: GrantLock;
  onToggle: (id: string) => void;
  direction: Direction;
  highlight?: boolean;
}) {
  const groups = groupPermissionItems(perms);

  return (
    <ColumnShell title={title} highlight={highlight}>
      <div className="space-y-3">
        {groups.length === 0 ? <EmptyRow text="—" /> : null}
        {groups.map((group) => (
          <div key={group.group} className="space-y-1">
            <div className="flex items-center gap-2 px-0.5">
              <span className="text-xs font-medium">{group.groupPt}</span>
              <span className="text-muted-foreground text-[10px]">({group.items.length})</span>
            </div>
            {group.items.map((perm) => {
              const meta = verbMeta(perm.permission);
              const Icon = meta.icon;
              const isLocked = lock.isPermLocked(perm);
              const row = (
                <div
                  key={perm.permission}
                  className={cn(
                    "group flex items-center justify-between gap-2 rounded-md border p-2 transition-all",
                    isLocked
                      ? "bg-muted/40 cursor-not-allowed opacity-40"
                      : "hover:bg-accent cursor-pointer"
                  )}
                  onClick={() => !isLocked && onToggle(perm.permission)}
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <Badge
                      variant="outline"
                      className={cn("h-5 shrink-0 gap-1 px-1.5 font-normal", meta.badgeClass)}
                    >
                      <Icon className="h-3 w-3" />
                      {meta.label}
                    </Badge>
                    <div className="min-w-0">
                      <span className="block truncate text-sm">{perm.pt}</span>
                      <code className="text-muted-foreground text-[10px]">{perm.permission}</code>
                    </div>
                  </div>
                  <DirectionChevron direction={direction} />
                </div>
              );
              if (isLocked) {
                return (
                  <TooltipProvider key={perm.permission}>
                    <Tooltip>
                      <TooltipTrigger asChild>{row}</TooltipTrigger>
                      <TooltipContent>
                        <p className="text-xs">{lock.permLockMessage(perm)}</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                );
              }
              return row;
            })}
          </div>
        ))}
      </div>
    </ColumnShell>
  );
}
