import { buildChatGptBuilderUrl } from "@/components/agent-config/chatgpt-builder-prompt";
import { MarkdownPreview } from "@/components/agent-config/MarkdownPreview";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { MAX_PROMPT_MARKDOWN_CHARS } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ExternalLink, Pencil, Save, Sparkles } from "lucide-react";
import { useState } from "react";

const STEPS = [
  "Clique em Montar com o ChatGPT e responda as perguntas dele sobre o seu negócio.",
  "No fim, ele entrega um texto pronto. Copie esse texto inteiro.",
  "Cole no campo abaixo e clique em Salvar nova versão.",
] as const;

const countFormat = new Intl.NumberFormat("pt-BR");

interface InstructionsCardProps {
  /** Text of the active version. Empty = never configured. */
  markdown: string;
  /** Optional business name pre-filled in the ChatGPT builder prompt. */
  businessName?: string;
  saving: boolean;
  onSave: (markdown: string) => void;
}

/**
 * Tenant agent instructions: built in ChatGPT, pasted here, shown rendered once saved.
 *
 * The parent mounts this card with `key={activeVersion}`, so saving or restoring a version
 * remounts it in read mode with the new text, while a failed save keeps the draft on screen.
 */
export function InstructionsCard({
  markdown,
  businessName = "",
  saving,
  onSave,
}: InstructionsCardProps) {
  const hasSaved = markdown.trim().length > 0;
  const [editing, setEditing] = useState(!hasSaved);
  const [draft, setDraft] = useState(markdown);

  const tooLong = draft.length > MAX_PROMPT_MARKDOWN_CHARS;
  const canSave = !saving && !tooLong && draft.trim().length > 0 && draft !== markdown;

  const cancel = () => {
    setDraft(markdown);
    setEditing(false);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Instruções do agente</CardTitle>
        <CardDescription>
          O que o agente precisa saber sobre o negócio e como ele deve falar. Este texto é somado ao
          comportamento-base do agente.
        </CardDescription>
        {!editing && (
          <CardAction>
            <Button type="button" variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Pencil className="size-3.5" />
              Editar
            </Button>
          </CardAction>
        )}
      </CardHeader>
      <CardContent>
        {editing ? (
          <div className="space-y-5">
            <ol className="max-w-2xl space-y-3">
              {STEPS.map((step, index) => (
                <li key={step} className="flex gap-3 text-sm">
                  <span className="bg-primary text-primary-foreground flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-medium tabular-nums">
                    {index + 1}
                  </span>
                  <span className="pt-0.5">{step}</span>
                </li>
              ))}
            </ol>

            <Button asChild variant="outline">
              <a
                href={buildChatGptBuilderUrl(businessName)}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Sparkles className="size-4" />
                Montar com o ChatGPT
                <ExternalLink className="text-muted-foreground size-3.5" />
              </a>
            </Button>

            <div className="space-y-1.5">
              <Label htmlFor="agent-instructions">Texto do ChatGPT</Label>
              <Textarea
                id="agent-instructions"
                value={draft}
                disabled={saving}
                aria-invalid={tooLong || undefined}
                className="max-h-[32rem] min-h-64 overflow-y-auto font-mono text-base md:text-sm"
                placeholder="Cole aqui o texto que o ChatGPT entregou."
                onChange={(event) => setDraft(event.target.value)}
              />
              <p
                className={cn(
                  "text-xs tabular-nums",
                  tooLong ? "text-destructive" : "text-muted-foreground"
                )}
              >
                {countFormat.format(draft.length)} de{" "}
                {countFormat.format(MAX_PROMPT_MARKDOWN_CHARS)} caracteres
                {tooLong && " — encurte o texto para salvar."}
              </p>
            </div>

            <div className="flex flex-wrap justify-end gap-2">
              {hasSaved && (
                <Button type="button" variant="ghost" disabled={saving} onClick={cancel}>
                  Cancelar
                </Button>
              )}
              <Button type="button" disabled={!canSave} onClick={() => onSave(draft)}>
                <Save className="size-3.5" />
                {saving ? "Salvando..." : "Salvar nova versão"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="bg-muted/30 rounded-md border p-4 text-sm leading-relaxed">
            <MarkdownPreview source={markdown} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
