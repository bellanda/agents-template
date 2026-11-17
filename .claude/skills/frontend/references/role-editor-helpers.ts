// Canonical (frontend gate, permissions-display.md §Funções personalizadas). Lands at `components/roles/role-editor-helpers.ts`.
// Generic: no project identity; project-specific wiring lives in the hooks (`useAdminPermissions`).
import type { AdminRole } from "@/types/admin";

/** Valor do Select "começar a partir de" para a função em branco (Radix não aceita `""`). */
export const BLANK_BASE = "__blank__";

const HTTP_CONFLICT = 409;

export interface RoleDraft {
  permissions: string[];
  /** Quantas permissões da base ficaram de fora porque quem edita não pode concedê-las. */
  skipped: number;
  basedOn: string | null;
}

/**
 * A função da qual a nova herda o "tipo" (usado pelo backend para regras por papel, ex.: ranking
 * de vendedor): a própria chave se a base é padrão; senão a base da base.
 */
export function resolveBasedOn(base: AdminRole): string | null {
  return base.isDefault ? base.id : (base.basedOn ?? null);
}

/** Copia as permissões da base, descartando as que o autor não tem (o backend recusaria). */
export function buildRoleDraft(
  base: AdminRole,
  canGrant: (permission: string) => boolean
): RoleDraft {
  const permissions = base.permissions.filter(canGrant);
  return {
    permissions,
    skipped: base.permissions.length - permissions.length,
    basedOn: resolveBasedOn(base),
  };
}

export interface RoleInUseInfo {
  message: string;
  members: string[];
  invites: string[];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function asNameList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (typeof item === "string") return item;
      const record = asRecord(item);
      const name = record?.fullName ?? record?.full_name ?? record?.name ?? record?.email;
      return typeof name === "string" ? name : "";
    })
    .filter(Boolean);
}

/**
 * Lê o 409 de `DELETE …/roles/{key}`: o backend recusa função em uso e lista quem a usa. Aceita
 * a lista em `details` (corpo cru, snake_case) ou dentro de `detail` objeto; sem lista, devolve só
 * a mensagem. `null` = não é esse erro.
 */
export function readRoleInUseError(error: unknown): RoleInUseInfo | null {
  const err = asRecord(error);
  if (!err || err.status !== HTTP_CONFLICT) return null;
  const details = asRecord(err.details) ?? asRecord(err.message) ?? {};
  const message =
    typeof err.message === "string"
      ? err.message
      : typeof details.message === "string"
        ? details.message
        : "Há membros usando esta função.";
  return {
    message,
    members: asNameList(details.members),
    invites: asNameList(details.invites),
  };
}
