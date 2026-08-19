// ConfirmDialog — canonical source (reference do gate frontend).
// Cross-project standard (gate frontend, ref overlays.md). Vendored por projeto em
// components/ui/confirm-dialog.tsx. Requer o primitivo shadcn `ui/alert-dialog.tsx`.
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Botão de ação em vermelho (delete/archive/remove). */
  destructive?: boolean;
  /** Mutation em curso: desabilita os botões e mostra `pendingLabel`. O dialog NÃO
   *  fecha sozinho enquanto `busy` — feche via `onOpenChange(false)` no `onSuccess`. */
  busy?: boolean;
  pendingLabel?: string;
  onConfirm: () => void;
}

/**
 * Confirmação destrutiva central — ÚNICO padrão de confirm do app.
 * AlertDialog (sem dismiss por click-fora, força uma escolha). NUNCA confirme delete
 * com tira inline, accordion, button-swap na linha, `window.confirm` ou Dialog ad-hoc.
 *
 * Padrão de uso em lista: um único ConfirmDialog no nível do container, controlado
 * pelo item selecionado.
 *   const [toDelete, setToDelete] = useState<Doc | null>(null);
 *   <ConfirmDialog
 *     open={!!toDelete}
 *     onOpenChange={(o) => !o && setToDelete(null)}
 *     title="Excluir documento?"
 *     description="Esta ação não pode ser desfeita."
 *     confirmLabel="Excluir"
 *     destructive
 *     busy={del.isPending}
 *     onConfirm={() =>
 *       toDelete && del.mutate(toDelete.id, { onSuccess: () => setToDelete(null) })
 *     }
 *   />
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  destructive = false,
  busy = false,
  pendingLabel,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>{cancelLabel}</AlertDialogCancel>
          <Button variant={destructive ? "destructive" : "default"} disabled={busy} onClick={onConfirm}>
            {busy ? (pendingLabel ?? "Processando...") : confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
