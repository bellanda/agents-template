// Canonical (frontend gate, permissions-display.md §Funções personalizadas). Lands at `components/roles/__tests__/role-editor-helpers.test.ts`.
// Generic: no project identity; project-specific wiring lives in the hooks (`useAdminPermissions`).
import {
  buildRoleDraft,
  readRoleInUseError,
  resolveBasedOn,
} from "@/components/roles/role-editor-helpers";
import type { AdminRole } from "@/types/admin";
import { describe, expect, it } from "vitest";

const VENDEDOR: AdminRole = {
  id: "vendedor",
  name: "Vendedor",
  permissions: ["vehicle:read", "lead:read", "finance:read"],
  isDefault: true,
};
const LAVADOR: AdminRole = {
  id: "lavador",
  name: "Lavador",
  permissions: ["vehicle:read"],
  isDefault: false,
  basedOn: "vendedor",
};

describe("resolveBasedOn", () => {
  it("função padrão vira a própria chave; personalizada herda a base dela", () => {
    expect(resolveBasedOn(VENDEDOR)).toBe("vendedor");
    expect(resolveBasedOn(LAVADOR)).toBe("vendedor");
    expect(resolveBasedOn({ ...LAVADOR, basedOn: null })).toBeNull();
  });
});

describe("buildRoleDraft", () => {
  it("copia só as permissões que o autor pode conceder e conta as que ficaram de fora", () => {
    const draft = buildRoleDraft(VENDEDOR, (p) => p !== "finance:read");
    expect(draft).toEqual({
      permissions: ["vehicle:read", "lead:read"],
      skipped: 1,
      basedOn: "vendedor",
    });
  });
});

describe("readRoleInUseError", () => {
  it("lê membros e convites do corpo cru do 409", () => {
    const info = readRoleInUseError({
      status: 409,
      message: "Função em uso",
      details: { members: [{ full_name: "Ana Dias" }, "João"], invites: [{ email: "x@y.com" }] },
    });
    expect(info).toEqual({
      message: "Função em uso",
      members: ["Ana Dias", "João"],
      invites: ["x@y.com"],
    });
  });

  it("ignora erro que não é 409", () => {
    expect(readRoleInUseError({ status: 403, message: "x" })).toBeNull();
    expect(readRoleInUseError(new Error("boom"))).toBeNull();
  });
});
