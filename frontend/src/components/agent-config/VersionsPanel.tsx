import {
  formatVersionDateTime,
  type AgentVersionItem,
} from "@/components/agent-config/agent-version";
import { VersionPreviewDialog } from "@/components/agent-config/VersionPreviewDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { Eye, History, RotateCcw } from "lucide-react";
import { useState } from "react";

interface VersionsPanelProps {
  /** Newest first. */
  versions: AgentVersionItem[];
  activeVersion: number;
  isLoading?: boolean;
  /** False = view-only (no manage permission): "Restaurar" is hidden everywhere. Default true. */
  canActivate?: boolean;
  /** Version currently being restored (null = idle). */
  activatingVersion: number | null;
  onActivate: (version: number) => void;
}

/**
 * Version history: preview/diff any version, restore it.
 *
 * Restoring creates a NEW version on the backend (history is immutable), so it needs no confirm
 * dialog: nothing is lost and it can be undone by restoring the previous one.
 *
 * Row layout is a grid so it reads on a 375px screen without a table: version + date on the first
 * line, the note on its own line, actions right-aligned; from `md` it becomes one row.
 */
export function VersionsPanel({
  versions,
  activeVersion,
  isLoading,
  canActivate = true,
  activatingVersion,
  onActivate,
}: VersionsPanelProps) {
  const [previewVersionNumber, setPreviewVersionNumber] = useState<number | null>(null);
  const previewVersion = versions.find((item) => item.version === previewVersionNumber) ?? null;
  const activeItem = versions.find((item) => item.version === activeVersion) ?? null;

  const handleActivate = (version: number) => {
    setPreviewVersionNumber(null);
    onActivate(version);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="size-4" />
          Histórico de versões
        </CardTitle>
        <CardDescription>
          Veja o que mudou em uma versão anterior e restaure se precisar.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : versions.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            Nenhuma versão salva ainda. Salve as instruções para criar a primeira.
          </p>
        ) : (
          <ul className="divide-y">
            {versions.map((item) => (
              <li
                key={item.version}
                className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 py-2.5 text-sm md:grid-cols-[5rem_minmax(0,1fr)_auto_auto]"
              >
                <span className="flex items-center gap-2 font-medium max-md:col-start-1 max-md:row-start-1">
                  v{item.version}
                  {item.version === activeVersion && <Badge className="h-4 px-1.5">Atual</Badge>}
                </span>
                <span
                  className={cn(
                    "text-muted-foreground min-w-0 max-md:col-span-2 max-md:row-start-2 md:truncate",
                    // No note: the "—" only keeps the desktop columns aligned; on mobile it is noise.
                    item.note === null && "max-md:hidden"
                  )}
                >
                  {item.note ?? "—"}
                </span>
                <span className="text-muted-foreground text-xs tabular-nums max-md:col-start-2 max-md:row-start-1">
                  {formatVersionDateTime(item.createdAt)}
                </span>
                <div className="flex justify-end gap-1 max-md:col-span-2 max-md:row-start-3">
                  <Button
                    type="button"
                    variant="ghost"
                    className="max-md:h-10"
                    onClick={() => setPreviewVersionNumber(item.version)}
                  >
                    <Eye />
                    Ver
                  </Button>
                  {canActivate && (
                    <Button
                      type="button"
                      variant="ghost"
                      className="max-md:h-10"
                      disabled={item.version === activeVersion || activatingVersion !== null}
                      onClick={() => onActivate(item.version)}
                    >
                      <RotateCcw />
                      {activatingVersion === item.version ? "Restaurando..." : "Restaurar"}
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      <VersionPreviewDialog
        version={previewVersion}
        activeVersion={activeItem}
        canActivate={canActivate}
        activating={activatingVersion !== null}
        onClose={() => setPreviewVersionNumber(null)}
        onActivate={handleActivate}
      />
    </Card>
  );
}
