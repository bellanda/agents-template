import type { AdminPermission, AdminRole } from "@/types/admin";
import { verbMeta } from "./permissionVerbs";

/** Combining diacritical marks — o que sobra do NFD depois de separar a letra do acento. */
const DIACRITICS = /[̀-ͯ]/g;

/** Minúsculas sem acento — "veículos" e "veiculos" têm que casar nos dois sentidos. */
export function normalizeText(value: string): string {
  return value.normalize("NFD").replace(DIACRITICS, "").toLowerCase();
}

/**
 * Casa a permissão pelo label pt-BR, pela chave crua, pelo nome do grupo e pelo label do verbo —
 * quem digita "veic" acha "Veículos", quem digita "excluir" acha o verbo, e quem cola
 * `vehicle:read` acha o item. Query vazia casa tudo.
 */
export function matchesPermission(perm: AdminPermission, query: string): boolean {
  const q = normalizeText(query.trim());
  if (!q) return true;
  const haystack = normalizeText(
    `${perm.pt} ${perm.permission} ${perm.groupPt} ${verbMeta(perm.permission).label}`
  );
  return haystack.includes(q);
}

/** Casa a função pelo nome, pela chave e pela descrição. */
export function matchesRole(role: AdminRole, query: string): boolean {
  const q = normalizeText(query.trim());
  if (!q) return true;
  return normalizeText(`${role.name} ${role.id} ${role.description ?? ""}`).includes(q);
}
