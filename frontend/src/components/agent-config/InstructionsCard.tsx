import {
  buildChatGptBuilderUrl,
  type ChatGptBuilderContext,
} from "@/components/agent-config/chatgpt-builder-prompt";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { ExternalLink, Pencil, Save, Sparkles } from "lucide-react";
import { memo, useMemo, useState } from "react";

const STEPS = [
  "Clique em Montar com o ChatGPT e responda as perguntas dele sobre o seu negócio.",
  "No fim, ele entrega um texto pronto. Copie esse texto inteiro.",
  "Cole no campo abaixo e clique em Salvar nova versão.",
] as const;

// Mirrors MAX_NOTE_CHARS in backend schemas/agents/agent_config.py (the note is only a label).
const NOTE_MAX_LENGTH = 500;

const countFormat = new Intl.NumberFormat("pt-BR");

/**
 * The ChatGPT link is its own memo'd component: the card re-renders on every keystroke and the
 * URL (a ~3k-char encode) only depends on the context, which the parent keeps stable.
 */
const ChatGptBuilderButton = memo(function ChatGptBuilderButton({
  builderContext,
}: {
  builderContext: ChatGptBuilderContext | undefined;
}) {
  const href = useMemo(() => buildChatGptBuilderUrl(builderContext), [builderContext]);
  return (
    <Button asChild variant="outline" className="max-md:h-11">
      <a href={href} target="_blank" rel="noopener noreferrer">
        <Sparkles />
        Montar com o ChatGPT
        <ExternalLink className="text-muted-foreground" />
      </a>
    </Button>
  );
});

interface InstructionsCardProps {
  /** Text of the active version. Empty = never configured. */
  markdown: string;
  /** Character cap; mirror the backend limit (`MAX_PROMPT_MARKDOWN_CHARS`). */
  maxChars: number;
  /** Domain text for the ChatGPT builder prompt. Keep the object reference stable. */
  builderContext?: ChatGptBuilderContext;
  saving: boolean;
  /** View-only (no manage permission): no "Editar", the saved text is just shown. */
  readOnly?: boolean;
  title?: string;
  description?: string;
  /** `note` is the optional publish note shown in the version history (undefined = none). */
  onSave: (markdown: string, note: string | undefined) => void;
}

/**
 * Tenant agent instructions: built in ChatGPT, pasted here, shown rendered once saved.
 *
 * The parent mounts this card with `key={activeVersion}`, so saving or restoring a version
 * remounts it in read mode with the new text, while a failed save keeps the draft (and the note)
 * on screen. Gate frontend, ref agent-instructions.md: one Markdown, no guided/advanced modes.
 */
export function InstructionsCard({
  markdown,
  maxChars,
  builderContext,
  saving,
  readOnly = false,
  title = "Instruções do agente",
  description = "O que o agente precisa saber sobre o negócio e como ele deve falar. Este texto é somado ao comportamento-base do agente.",
  onSave,
}: InstructionsCardProps) {
  const hasSaved = markdown.trim().length > 0;
  const [editing, setEditing] = useState(!hasSaved && !readOnly);
  const [draft, setDraft] = useState(markdown);
  const [note, setNote] = useState("");

  const tooLong = draft.length > maxChars;
  const canSave = !saving && !tooLong && draft.trim().length > 0 && draft !== markdown;

  const cancel = () => {
    setDraft(markdown);
    setNote("");
    setEditing(false);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
        {!editing && !readOnly && (
          <CardAction>
            <Button type="button" variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Pencil />
              Editar
            </Button>
          </CardAction>
        )}
      </CardHeader>
      <CardContent>
        {editing ? (
          <div className="space-y-5">
            {/* Sequential steps = one column, group width contained (gate frontend, grid-vs-stack). */}
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

            <ChatGptBuilderButton builderContext={builderContext} />

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
                {countFormat.format(draft.length)} de {countFormat.format(maxChars)} caracteres
                {tooLong && " — encurte o texto para salvar."}
              </p>
            </div>

            <div className="max-w-xl space-y-1.5">
              <Label htmlFor="agent-instructions-note">Nota da versão (opcional)</Label>
              <Input
                id="agent-instructions-note"
                value={note}
                disabled={saving}
                maxLength={NOTE_MAX_LENGTH}
                className="text-base max-md:h-11 md:text-sm"
                placeholder="Ex.: novo horário de funcionamento"
                onChange={(event) => setNote(event.target.value)}
              />
            </div>

            <div className="flex flex-wrap justify-end gap-2">
              {hasSaved && (
                <Button
                  type="button"
                  variant="ghost"
                  className="max-md:h-11"
                  disabled={saving}
                  onClick={cancel}
                >
                  Cancelar
                </Button>
              )}
              <Button
                type="button"
                className="max-md:h-11"
                disabled={!canSave}
                onClick={() => onSave(draft, note.trim() || undefined)}
              >
                <Save />
                {saving ? "Salvando..." : "Salvar nova versão"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="bg-muted/30 rounded-md border p-4 text-sm leading-relaxed">
            <MarkdownPreview source={markdown} emptyHint="O agente ainda não foi configurado." />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
