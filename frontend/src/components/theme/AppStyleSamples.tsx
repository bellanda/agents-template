import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { ToggleCard } from "@/components/ui/toggle-card";
import type { ReactNode } from "react";

/**
 * Sample components for the Appearance dialog, in the spirit of Shadcn Create (2026-11-09).
 *
 * Generic on purpose and identical in every app: domain content belongs in `AppStylePreview`.
 * Uses the real components so style and font size look exactly as in the app. The caller wraps
 * this in `inert`, so nothing here takes focus or clicks. The grid adapts to the font size.
 */
export function AppStyleSamples() {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,14rem),1fr))] gap-3">
      <SampleCard title="Texto">
        <p className="text-lg leading-tight font-bold">Título da tela</p>
        <p className="text-sm">Texto normal, como o de listas e formulários.</p>
        <p className="text-muted-foreground text-xs">Texto menor, como o de legendas.</p>
      </SampleCard>
      <SampleCard title="Botões">
        <div className="flex flex-wrap gap-2">
          <Button size="sm">Principal</Button>
          <Button size="sm" variant="secondary">
            Secundário
          </Button>
          <Button size="sm" variant="outline">
            Contorno
          </Button>
          <Button size="sm" variant="destructive">
            Excluir
          </Button>
        </div>
      </SampleCard>
      <SampleCard title="Formulário">
        <Label className="flex-col items-start gap-1.5">
          Nome
          <Input defaultValue="Maria Souza" />
        </Label>
        <ToggleCard size="compact" checked onCheckedChange={() => {}} title="Receber avisos" />
      </SampleCard>
      <SampleCard title="Etiquetas e progresso">
        <div className="flex flex-wrap gap-1.5">
          <Badge>Novo</Badge>
          <Badge variant="secondary">Em andamento</Badge>
          <Badge variant="outline">Rascunho</Badge>
          <Badge variant="destructive">Atrasado</Badge>
        </div>
        <Progress value={64} aria-label="Progresso de exemplo" />
      </SampleCard>
    </div>
  );
}

function SampleCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="bg-card text-card-foreground min-w-0 space-y-2.5 rounded-xl border p-3 shadow-sm">
      <p className="text-muted-foreground text-xs font-medium">{title}</p>
      {children}
    </div>
  );
}
