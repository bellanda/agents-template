// Canonical (frontend gate, permissions-display.md §Funções personalizadas). Lands at `components/roles/RoleEditorDialog.tsx`.
// Generic: no project identity; project-specific wiring lives in the hooks (`useAdminPermissions`).
import { RolePermissionPicker } from "@/components/roles/RolePermissionPicker";
import { BLANK_BASE, buildRoleDraft, resolveBasedOn } from "@/components/roles/role-editor-helpers";
import type { PermItem } from "@/components/members/types";
import { Button } from "@/components/ui/button";
import { FormDialog } from "@/components/ui/form-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { AdminRole, CreateRoleRequest } from "@/types/admin";
import { useState } from "react";
import { LuLoaderCircle } from "react-icons/lu";

interface RoleEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Ausente = criar. Presente = editar (só personalizada). */
  role?: AdminRole | null;
  /** Todas as funções da org — fonte do "começar a partir de…". */
  roles: AdminRole[];
  catalog: PermItem[];
  canGrant: (permission: string) => boolean;
  pending: boolean;
  onSubmit: (payload: CreateRoleRequest) => void;
}

/**
 * Criar/editar função personalizada. O pai monta o dialog só enquanto aberto (estado inicial vem
 * das props — sem `useEffect` de sincronização).
 */
export function RoleEditorDialog({
  open,
  onOpenChange,
  role,
  roles,
  catalog,
  canGrant,
  pending,
  onSubmit,
}: RoleEditorDialogProps) {
  const isEdit = Boolean(role);
  const [label, setLabel] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [permissions, setPermissions] = useState<string[]>(role?.permissions ?? []);
  const [baseKey, setBaseKey] = useState(BLANK_BASE);
  const [basedOn, setBasedOn] = useState<string | null>(role?.basedOn ?? null);
  const [skipped, setSkipped] = useState(0);

  // Quem não tem todas as permissões de uma função não pode editá-la (regra do backend).
  const missingOnEdit = isEdit && role!.permissions.some((p) => !canGrant(p));

  const pickBase = (key: string) => {
    setBaseKey(key);
    const base = roles.find((r) => r.id === key);
    if (!base) {
      setPermissions([]);
      setBasedOn(null);
      setSkipped(0);
      return;
    }
    const draft = buildRoleDraft(base, canGrant);
    setPermissions(draft.permissions);
    setBasedOn(resolveBasedOn(base));
    setSkipped(draft.skipped);
  };

  const canSave = label.trim().length > 0 && !missingOnEdit && !pending;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSave) return;
    onSubmit({
      label: label.trim(),
      description: description.trim(),
      permissions,
      ...(isEdit ? {} : { basedOn }),
    });
  };

  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title={isEdit ? "Editar função" : "Nova função"}
      description="Defina o que a função permite. Quem recebe a função herda só estas permissões."
      size="xl"
      busy={pending}
      onSubmit={handleSubmit}
      bodyClassName="space-y-4"
      footer={
        <Button type="submit" disabled={!canSave}>
          {pending ? <LuLoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : null}
          {isEdit ? "Salvar" : "Criar função"}
        </Button>
      }
    >
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="role-label">Nome</Label>
          <Input
            id="role-label"
            value={label}
            maxLength={60}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Ex.: Lavador"
          />
        </div>
        {isEdit ? null : (
          <div className="space-y-1.5">
            <Label>Começar a partir de…</Label>
            <Select value={baseKey} onValueChange={pickBase}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={BLANK_BASE}>Em branco</SelectItem>
                {roles.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.name}
                    {r.isDefault ? " (padrão)" : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="role-description">Descrição</Label>
        <Textarea
          id="role-description"
          value={description}
          rows={2}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Para que serve esta função"
        />
      </div>
      {skipped > 0 ? (
        <p className="text-muted-foreground text-xs">
          {skipped} permissão(ões) da função escolhida ficaram de fora porque você não as tem.
        </p>
      ) : null}
      {missingOnEdit ? (
        <p className="text-destructive text-xs">
          Esta função tem permissões que você não possui, então só quem as tem pode editá-la.
        </p>
      ) : null}
      <RolePermissionPicker
        catalog={catalog}
        selected={permissions}
        onChange={setPermissions}
        canGrant={canGrant}
      />
    </FormDialog>
  );
}
