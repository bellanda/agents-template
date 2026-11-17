// Canonical (frontend gate, permissions-display.md §Funções personalizadas). Lands at `components/roles/RolePermissionPicker.tsx`.
// Generic: no project identity; project-specific wiring lives in the hooks (`useAdminPermissions`).
import { PermissionSearchInput } from "@/components/members/PermissionSearchInput";
import { PermColumn } from "@/components/members/PermissionPickerColumns";
import { matchesPermission } from "@/components/members/permissionSearch";
import { NO_LOCK, type GrantLock, type PermItem } from "@/components/members/types";
import { useMemo, useState } from "react";

interface RolePermissionPickerProps {
  catalog: PermItem[];
  selected: string[];
  onChange: (next: string[]) => void;
  /** Só concede quem tem: permissão que o autor não tem fica travada (o backend também recusa). */
  canGrant: (permission: string) => boolean;
}

const LOCK_MESSAGE = "Você não tem esta permissão, então não pode concedê-la a uma função.";

/** Dual-list agrupado por domínio com busca única — mesmo display da aba Permissões do membro. */
export function RolePermissionPicker({
  catalog,
  selected,
  onChange,
  canGrant,
}: RolePermissionPickerProps) {
  const [query, setQuery] = useState("");
  const lock: GrantLock = useMemo(
    () => ({
      ...NO_LOCK,
      isPermLocked: (perm) => !canGrant(perm.permission),
      permLockMessage: () => LOCK_MESSAGE,
    }),
    [canGrant]
  );
  const visible = useMemo(
    () => catalog.filter((p) => matchesPermission(p, query)),
    [catalog, query]
  );
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  const toggle = (permission: string) =>
    onChange(
      selectedSet.has(permission)
        ? selected.filter((p) => p !== permission)
        : [...selected, permission]
    );

  return (
    <div className="space-y-3">
      <PermissionSearchInput
        value={query}
        onChange={setQuery}
        placeholder="Buscar permissão por nome, chave, conjunto ou verbo…"
      />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="h-72 md:h-96">
          <PermColumn
            title="Disponíveis"
            perms={visible.filter((p) => !selectedSet.has(p.permission))}
            lock={lock}
            onToggle={toggle}
            direction="add"
          />
        </div>
        <div className="h-72 md:h-96">
          <PermColumn
            title={`Na função (${selected.length})`}
            highlight
            perms={visible.filter((p) => selectedSet.has(p.permission))}
            lock={lock}
            onToggle={toggle}
            direction="remove"
          />
        </div>
      </div>
    </div>
  );
}
