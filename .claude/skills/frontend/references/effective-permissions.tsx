import { ShieldCheck } from "lucide-react";
import { useMemo } from "react";
import { matchesPermission } from "./permissionSearch";
import { PermissionGroupList } from "./PermissionGroupList";
import type { PermItem, RoleItem } from "./types";

interface EffectivePermissionsProps {
  allRoles: RoleItem[];
  allPermissions: PermItem[];
  selectedRoleIds: string[];
  permissionOverrides: string[];
  /** Membro é superusuário da plataforma → tem TUDO, independente de papel na org. */
  isSuperuser?: boolean;
  /** Filtro da barra de busca da aba. */
  query?: string;
}

/**
 * Computes the effective permissions a user will have given their roles + overrides.
 * Mirrors backend `permission_service.resolve_membership_permissions`: union of
 * permissions from selected roles, plus any explicit overrides.
 *
 * Superusuário é o caso que NÃO passa por essa conta: o bypass mora em
 * `AuthContext.has_permission`, que devolve `True` antes de olhar a membership. Somar só
 * papéis+overrides renderiza "nenhuma permissão" justamente pra quem pode tudo.
 */
export function EffectivePermissions({
  allRoles,
  allPermissions,
  selectedRoleIds,
  permissionOverrides,
  isSuperuser = false,
  query = "",
}: EffectivePermissionsProps) {
  const { effective, fromOverridesOnly } = useMemo(() => {
    if (isSuperuser) {
      return {
        effective: allPermissions.map((p) => p.permission),
        fromOverridesOnly: new Set<string>(),
      };
    }
    const roleSet = new Set(selectedRoleIds);
    const fromRoles = new Set<string>();
    for (const role of allRoles) {
      if (roleSet.has(role.id)) {
        for (const p of role.permissions) fromRoles.add(p);
      }
    }
    const overrideSet = new Set(permissionOverrides);
    const union = new Set<string>([...fromRoles, ...overrideSet]);
    const fromOverridesOnly = new Set<string>();
    for (const p of overrideSet) if (!fromRoles.has(p)) fromOverridesOnly.add(p);
    return {
      effective: Array.from(union).sort(),
      fromOverridesOnly,
    };
  }, [allRoles, allPermissions, selectedRoleIds, permissionOverrides, isSuperuser]);

  const visible = useMemo(() => {
    if (!query.trim()) return effective;
    const byKey = new Map(allPermissions.map((p) => [p.permission, p]));
    return effective.filter((key) => {
      const item = byKey.get(key);
      return item ? matchesPermission(item, query) : false;
    });
  }, [effective, allPermissions, query]);

  if (effective.length === 0) {
    return (
      <div className="text-muted-foreground rounded-md border border-dashed p-4 text-center text-xs">
        Nenhuma permissão efetiva — selecione uma função ou adicione overrides para liberar acesso.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {isSuperuser ? (
        <div className="border-primary/30 bg-primary/5 flex items-start gap-2 rounded-md border p-3">
          <ShieldCheck className="text-primary mt-0.5 h-4 w-4 shrink-0" />
          <p className="text-xs">
            <strong>Superusuário da plataforma</strong> — acesso total, sem depender de função na
            organização. O backend libera antes de checar o RBAC, então funções e overrides abaixo
            não alteram o que este membro pode fazer.
          </p>
        </div>
      ) : null}
      <p className="text-muted-foreground text-xs">
        Total de permissões efetivas: <strong>{effective.length}</strong>
        {query.trim() ? ` · ${visible.length} no filtro` : ""}
        {" · "}
        {isSuperuser
          ? "todas do catálogo"
          : fromOverridesOnly.size > 0
            ? `${fromOverridesOnly.size} via override`
            : "tudo herdado das funções"}
      </p>
      <PermissionGroupList
        permissions={visible}
        catalog={allPermissions}
        overrideKeys={fromOverridesOnly}
        emptyText="Nenhuma permissão efetiva corresponde à busca."
      />
    </div>
  );
}
