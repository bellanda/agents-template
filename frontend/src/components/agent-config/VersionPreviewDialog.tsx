import {
  formatVersionDateTime,
  type AgentVersionItem,
} from "@/components/agent-config/agent-version";
import { MarkdownPreview } from "@/components/agent-config/MarkdownPreview";
import {
  collapseUnchanged,
  diffLines,
  hasChanges,
  type DiffRow,
} from "@/components/agent-config/text-diff";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { RotateCcw } from "lucide-react";
import { useMemo } from "react";

const ROW_STYLES = {
  same: { marker: " ", className: "text-muted-foreground", label: null },
  added: {
    marker: "+",
    className: "bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
    label: "Entra",
  },
  removed: {
    marker: "-",
    className: "bg-destructive/10 text-destructive",
    label: "Sai",
  },
} as const;

function DiffRowView({ row }: { row: DiffRow }) {
  if (row.kind === "gap") {
    return (
      <div className="text-muted-foreground bg-muted/40 px-2 py-0.5 text-center">
        {row.hiddenLines} {row.hiddenLines === 1 ? "linha igual" : "linhas iguais"}
      </div>
    );
  }
  const style = ROW_STYLES[row.kind];
  return (
    <div className={cn("flex gap-2 px-2", style.className)}>
      <span aria-hidden className="shrink-0 select-none">
        {style.marker}
      </span>
      {style.label && <span className="sr-only">{style.label}: </span>}
      <span className="min-h-[1lh] min-w-0 break-words whitespace-pre-wrap">{row.text}</span>
    </div>
  );
}

interface VersionDiffProps {
  /** Text live right now. */
  currentMarkdown: string;
  /** Text of the version being previewed (what the agent would use after restoring it). */
  versionMarkdown: string;
}

function VersionDiff({ currentMarkdown, versionMarkdown }: VersionDiffProps) {
  const lines = useMemo(
    () => diffLines(currentMarkdown, versionMarkdown),
    [currentMarkdown, versionMarkdown]
  );
  const rows = useMemo(() => collapseUnchanged(lines), [lines]);

  if (!hasChanges(lines)) {
    return <p className="text-muted-foreground text-sm">Texto idêntico ao da versão atual.</p>;
  }
  return (
    <div className="space-y-2">
      <p className="text-muted-foreground text-xs">
        Ao restaurar, o que está em vermelho sai do texto atual e o que está em verde entra.
      </p>
      <div className="overflow-hidden rounded-md border py-1 font-mono text-xs leading-relaxed">
        {rows.map((row, index) => (
          // Rows have no identity of their own; the list is static per (current, version) pair.
          <DiffRowView key={index} row={row} />
        ))}
      </div>
    </div>
  );
}

interface VersionPreviewDialogProps {
  /** Version being previewed; null = closed. */
  version: AgentVersionItem | null;
  /** The live version, diff baseline. Null when it is not in the loaded history. */
  activeVersion: AgentVersionItem | null;
  canActivate: boolean;
  activating: boolean;
  onClose: () => void;
  onActivate: (version: number) => void;
}

/**
 * Read-only look at a past version: rendered text, plus a line diff against the active one.
 *
 * Footer carries ONLY the affirmative action (gate frontend, overlays: a Dialog already closes
 * with the X / click-outside, so a "Fechar" button would be redundant). The dialog geometry is
 * set here because this template's `ui/dialog.tsx` base does not carry the canonical one
 * (`max-h` + single scroll + the `max-md` clamp); an app whose base has it can drop those classes.
 */
export function VersionPreviewDialog({
  version,
  activeVersion,
  canActivate,
  activating,
  onClose,
  onActivate,
}: VersionPreviewDialogProps) {
  const isActive = version !== null && version.version === activeVersion?.version;
  const showDiff = version !== null && activeVersion !== null && !isActive;

  return (
    <Dialog open={version !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto overscroll-contain max-md:max-h-[calc(100svh-3rem)] sm:max-w-3xl">
        {version && (
          <>
            <DialogHeader className="pr-8">
              <DialogTitle className="flex items-center gap-2">
                Versão {version.version}
                {isActive && <Badge className="h-4 px-1.5">Atual</Badge>}
              </DialogTitle>
              <DialogDescription>
                {formatVersionDateTime(version.createdAt)}
                {version.note ? ` — ${version.note}` : ""}
              </DialogDescription>
            </DialogHeader>

            <Tabs key={version.version} defaultValue="text">
              <TabsList>
                <TabsTrigger value="text">Texto</TabsTrigger>
                {showDiff && <TabsTrigger value="diff">Diferenças</TabsTrigger>}
              </TabsList>
              <TabsContent value="text" className="rounded-md border p-4 text-sm leading-relaxed">
                <MarkdownPreview source={version.markdown} emptyHint="Versão sem texto." />
              </TabsContent>
              {showDiff && (
                <TabsContent value="diff">
                  <VersionDiff
                    currentMarkdown={activeVersion.markdown}
                    versionMarkdown={version.markdown}
                  />
                </TabsContent>
              )}
            </Tabs>

            {canActivate && !isActive && (
              <DialogFooter>
                <Button
                  type="button"
                  className="max-md:h-11"
                  disabled={activating}
                  onClick={() => onActivate(version.version)}
                >
                  <RotateCcw />
                  {activating ? "Restaurando..." : "Restaurar esta versão"}
                </Button>
              </DialogFooter>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
