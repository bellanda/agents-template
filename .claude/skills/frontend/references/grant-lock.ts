import type { AdminPermission, AdminRole } from "@/types/admin";

export type RoleItem = AdminRole;
export type PermItem = AdminPermission;

/**
 * Gate de papel/permissão privilegiada no picker de concessão (skill frontend, ref
 * permissions-display.md).
 *
 * Existe porque `components/members/` é copiado entre projetos à mão: qualquer chave de papel
 * ("gestor", "owner") ou campo de projeto (`subscriptionActive`, `organizerStatus`) dentro de um
 * arquivo compartilhado vira fork silencioso na próxima cópia — sem erro de compilação, sem lint.
 * O predicado é montado UMA vez pelo `MemberDetailDialog` de cada projeto e desce como dado.
 */
export interface GrantLock {
  /** Papel de alto privilégio — ganha o escudo na lista, esteja liberado ou não. */
  isRolePrivileged: (role: RoleItem) => boolean;
  /** Privilegiado E o membro não é elegível → linha desabilitada + tooltip. */
  isRoleLocked: (role: RoleItem) => boolean;
  isPermLocked: (perm: PermItem) => boolean;
  roleLockMessage: (role: RoleItem) => string;
  permLockMessage: (perm: PermItem) => string;
}

export const NO_LOCK: GrantLock = {
  isRolePrivileged: () => false,
  isRoleLocked: () => false,
  isPermLocked: () => false,
  roleLockMessage: () => "",
  permLockMessage: () => "",
};
