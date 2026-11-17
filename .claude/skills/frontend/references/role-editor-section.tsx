// Canonical (frontend gate, permissions-display.md §Funções personalizadas). Lands at `components/settings/sections/RolesSection.tsx`.
// Generic: no project identity; project-specific wiring lives in the hooks (`useAdminPermissions`).
import { RoleInfoDialog } from "@/components/members/RoleInfoDialog";
import { RoleEditorDialog } from "@/components/roles/RoleEditorDialog";
import { readRoleInUseError } from "@/components/roles/role-editor-helpers";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminPermissions } from "@/hooks/useAdminPermissions";
import { useCurrentOrgRoles } from "@/hooks/useAuth";
import { notifyError } from "@/lib/api/notify";
import { PERMISSIONS, type Permission } from "@/lib/auth/permissions";
import type { AdminRole, CreateRoleRequest } from "@/types/admin";
import { useCallback, useState } from "react";
import { LuPencil, LuPlus, LuShieldPlus, LuTrash2 } from "react-icons/lu";
import { toast } from "sonner";

interface RoleInUse {
  role: AdminRole;
  message: string;
  members: string[];
  invites: string[];
}

function RoleCard({
  role,
  canEdit,
  onOpen,
  onEdit,
  onDelete,
}: {
  role: AdminRole;
  canEdit: boolean;
  onOpen: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const members = role.memberCount ?? 0;
  const showActions = canEdit && !role.isDefault;
  return (
    <div className="bg-card flex items-stretch rounded-lg border">
      <button
        type="button"
        onClick={role.isDefault || !canEdit ? onOpen : onEdit}
        className="hover:bg-accent/40 flex min-w-0 flex-1 flex-col gap-1 rounded-lg p-3 text-left transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="line-clamp-2 min-w-0 text-sm font-medium break-words">{role.name}</span>
          <Badge
            variant={role.isDefault ? "secondary" : "outline"}
            className={
              role.isDefault
                ? "h-4 shrink-0 px-1 text-[0.625rem]"
                : "border-primary/40 text-primary h-4 px-1 text-[0.625rem]"
            }
          >
            {role.isDefault ? "Padrão" : "Personalizada"}
          </Badge>
        </div>
        <p className="text-muted-foreground truncate text-xs">
          {role.description || "Sem descrição."}
        </p>
        <p className="text-muted-foreground text-xs tabular-nums">
          {role.permissions.length} permissões · {members} {members === 1 ? "membro" : "membros"}
        </p>
      </button>
      {showActions ? (
        <div className="flex shrink-0 items-center gap-1 pr-2">
          <Button
            variant="ghost"
            size="icon"
            className="size-9"
            onClick={onEdit}
            aria-label={`Editar ${role.name}`}
          >
            <LuPencil className="size-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="text-destructive size-9"
            onClick={onDelete}
            aria-label={`Excluir ${role.name}`}
          >
            <LuTrash2 className="size-4" />
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function RoleGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-3 @xl:grid-cols-2 @4xl:grid-cols-3">{children}</div>;
}

export function RolesSection({ orgId }: { orgId: string }) {
  const { can } = useCurrentOrgRoles();
  const canManage = can(PERMISSIONS.ROLE_MANAGE);
  const { useListRoles, useListPermissions, useCreateRole, useUpdateRole, useDeleteRole } =
    useAdminPermissions();
  const rolesQuery = useListRoles(orgId);
  const { data: catalog } = useListPermissions();
  const createMutation = useCreateRole(orgId);
  const updateMutation = useUpdateRole(orgId);
  const deleteMutation = useDeleteRole(orgId);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<AdminRole | null>(null);
  const [viewing, setViewing] = useState<AdminRole | null>(null);
  const [toDelete, setToDelete] = useState<AdminRole | null>(null);
  const [inUse, setInUse] = useState<RoleInUse | null>(null);

  // Só concede quem tem — o backend recusa o resto com 403, aqui já trava a escolha.
  const canGrant = useCallback((permission: string) => can(permission as Permission), [can]);

  const roles = rolesQuery.data ?? [];
  const defaults = roles.filter((r) => r.isDefault);
  const customs = roles.filter((r) => !r.isDefault);

  const openEditor = (role: AdminRole | null) => {
    setEditing(role);
    setEditorOpen(true);
  };

  const handleSubmit = (payload: CreateRoleRequest) => {
    const onSuccess = () => {
      toast.success(editing ? "Função atualizada" : "Função criada");
      setEditorOpen(false);
    };
    if (editing) {
      const { label, description, permissions } = payload;
      updateMutation.mutate(
        { key: editing.id, label, description, permissions },
        { onSuccess, onError: (e) => notifyError("Não foi possível salvar a função", e) }
      );
      return;
    }
    createMutation.mutate(payload, {
      onSuccess,
      onError: (e) => notifyError("Não foi possível criar a função", e),
    });
  };

  const handleDelete = () => {
    if (!toDelete) return;
    const role = toDelete;
    deleteMutation.mutate(role.id, {
      onSuccess: () => {
        toast.success("Função excluída");
        setToDelete(null);
      },
      onError: (error) => {
        setToDelete(null);
        const conflict = readRoleInUseError(error);
        if (conflict) setInUse({ role, ...conflict });
        else notifyError("Não foi possível excluir a função", error);
      },
    });
  };

  if (rolesQuery.isError) {
    return <ErrorState onRetry={() => rolesQuery.refetch()} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-muted-foreground text-sm">
          {defaults.length} padrão · {customs.length} personalizada(s)
        </div>
        {canManage ? (
          <Button size="sm" onClick={() => openEditor(null)} disabled={!catalog}>
            <LuPlus className="mr-2 h-4 w-4" />
            Nova função
          </Button>
        ) : null}
      </div>

      {rolesQuery.isLoading ? (
        <RoleGrid>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 rounded-lg" />
          ))}
        </RoleGrid>
      ) : (
        <>
          <section className="space-y-2">
            <h3 className="text-sm font-semibold">Funções personalizadas</h3>
            {customs.length === 0 ? (
              <div className="rounded-md border border-dashed">
                <EmptyState
                  icon={LuShieldPlus}
                  size="compact"
                  title="Nenhuma função personalizada"
                  description={
                    canManage
                      ? 'Use "Nova função" para criar, por exemplo, um acesso só de serviços.'
                      : "Fale com o administrador para criar funções sob medida."
                  }
                />
              </div>
            ) : (
              <RoleGrid>
                {customs.map((role) => (
                  <RoleCard
                    key={role.id}
                    role={role}
                    canEdit={canManage}
                    onOpen={() => setViewing(role)}
                    onEdit={() => openEditor(role)}
                    onDelete={() => setToDelete(role)}
                  />
                ))}
              </RoleGrid>
            )}
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold">Funções padrão</h3>
            <p className="text-muted-foreground text-xs">
              Fixas do sistema. Toque para ver o que cada uma permite; para ajustar, crie uma função
              a partir dela.
            </p>
            <RoleGrid>
              {defaults.map((role) => (
                <RoleCard
                  key={role.id}
                  role={role}
                  canEdit={false}
                  onOpen={() => setViewing(role)}
                  onEdit={() => undefined}
                  onDelete={() => undefined}
                />
              ))}
            </RoleGrid>
          </section>
        </>
      )}

      {editorOpen && catalog ? (
        <RoleEditorDialog
          key={editing?.id ?? "new"}
          open
          onOpenChange={setEditorOpen}
          role={editing}
          roles={roles}
          catalog={catalog}
          canGrant={canGrant}
          pending={createMutation.isPending || updateMutation.isPending}
          onSubmit={handleSubmit}
        />
      ) : null}

      {viewing && catalog ? (
        <RoleInfoDialog role={viewing} catalog={catalog} onClose={() => setViewing(null)} />
      ) : null}

      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
        title={`Excluir ${toDelete?.name ?? "função"}?`}
        description="Esta ação não pode ser desfeita."
        confirmLabel="Excluir"
        destructive
        busy={deleteMutation.isPending}
        onConfirm={handleDelete}
      />

      <ConfirmDialog
        open={inUse !== null}
        onOpenChange={(open) => !open && setInUse(null)}
        title={`${inUse?.role.name ?? "Função"} está em uso`}
        description={
          // O backend já manda a frase pronta (com nomes e "troque a função…"); só completa quando
          // vier uma lista estruturada ou uma mensagem sem o pedido de troca.
          inUse && /troque/i.test(inUse.message)
            ? inUse.message
            : `${inUse?.message ?? ""} Troque a função deles antes de excluir.`
        }
        confirmLabel="Entendi"
        cancelLabel="Fechar"
        onConfirm={() => setInUse(null)}
      >
        {inUse && (inUse.members.length > 0 || inUse.invites.length > 0) ? (
          <ul className="text-muted-foreground max-h-40 list-disc space-y-0.5 overflow-y-auto pl-5 text-sm">
            {inUse.members.map((name) => (
              <li key={`m-${name}`}>{name}</li>
            ))}
            {inUse.invites.map((email) => (
              <li key={`i-${email}`}>{email} (convite pendente)</li>
            ))}
          </ul>
        ) : null}
      </ConfirmDialog>
    </div>
  );
}
