import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { AgentConfigVersion } from "@/lib/api";
import { History, RotateCcw } from "lucide-react";

const dateTimeFormat = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

interface VersionsPanelProps {
  /** Newest first. */
  versions: AgentConfigVersion[];
  activeVersion: number;
  isLoading?: boolean;
  /** Version currently being restored (null = idle). */
  activatingVersion: number | null;
  onActivate: (version: number) => void;
}

/** Version history; restoring creates a NEW version on the backend (history is immutable). */
export function VersionsPanel({
  versions,
  activeVersion,
  isLoading,
  activatingVersion,
  onActivate,
}: VersionsPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="size-4" />
          Histórico de versões
        </CardTitle>
        <CardDescription>Restaure uma versão anterior das instruções.</CardDescription>
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
            {versions.map((version) => (
              <li key={version.version} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                <span className="flex min-w-16 items-center gap-2 font-medium">
                  v{version.version}
                  {version.version === activeVersion && <Badge className="h-4 px-1.5">Atual</Badge>}
                </span>
                <span className="text-muted-foreground min-w-0 flex-1 truncate">
                  {version.note ?? "—"}
                </span>
                <span className="text-muted-foreground text-xs tabular-nums">
                  {dateTimeFormat.format(new Date(version.created_at))}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={version.version === activeVersion || activatingVersion !== null}
                  onClick={() => onActivate(version.version)}
                >
                  <RotateCcw className="size-3" />
                  {activatingVersion === version.version ? "Restaurando..." : "Restaurar"}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
