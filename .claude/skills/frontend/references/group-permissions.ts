import type { AdminPermission } from "@/types/admin";
import { verbMeta } from "./permissionVerbs";

export interface PermissionGroup {
  group: string;
  groupPt: string;
  minOrder: number;
  items: AdminPermission[];
}

/**
 * Agrupa itens do catálogo por domínio na ordem canônica (skill frontend, ref
 * permissions-display.md): grupos ordenados pelo menor `order` do catálogo, itens dentro do grupo
 * pela ordem do VERBO. Fonte única para o display read-only (`PermissionGroupList`) e para as
 * colunas de concessão — se cada lado ordenasse por conta própria, a aba de conceder e a de
 * efetivas mostrariam a mesma permissão em posições diferentes.
 */
export function groupPermissionItems(items: AdminPermission[]): PermissionGroup[] {
  const grouped = new Map<string, PermissionGroup>();

  for (const item of items) {
    const existing = grouped.get(item.group);
    if (existing) {
      existing.items.push(item);
      existing.minOrder = Math.min(existing.minOrder, item.order);
    } else {
      grouped.set(item.group, {
        group: item.group,
        groupPt: item.groupPt,
        minOrder: item.order,
        items: [item],
      });
    }
  }

  const ordered = Array.from(grouped.values()).sort((a, b) => a.minOrder - b.minOrder);
  for (const g of ordered) {
    g.items.sort(
      (a, b) =>
        verbMeta(a.permission).order - verbMeta(b.permission).order ||
        a.permission.localeCompare(b.permission)
    );
  }
  return ordered;
}

/**
 * Mesma coisa a partir de chaves cruas. Chave ausente do catálogo é descartada — é o caso de um
 * override que ficou órfão depois de a permissão sair do backend.
 */
export function groupPermissions(
  permissions: string[],
  catalog: AdminPermission[]
): PermissionGroup[] {
  const byKey = new Map(catalog.map((p) => [p.permission, p]));
  const items: AdminPermission[] = [];
  for (const key of permissions) {
    const item = byKey.get(key);
    if (item) items.push(item);
  }
  return groupPermissionItems(items);
}
