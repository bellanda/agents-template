import { CHATGPT_URL } from "@/components/agent-config/chatgpt-builder-prompt";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Copy, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";

/**
 * Seconds between "prompt copied" and opening chatgpt.com. Long enough to read the instructions,
 * short enough to stay inside the browsers' popup window: `window.open` outside a click handler is
 * only allowed for ~5 s after the user gesture (Safari/iOS tolerate less), so do NOT raise this.
 * If the browser blocks it anyway the dialog falls back to a button (a real gesture).
 */
export const CHATGPT_OPEN_DELAY_SECONDS = 3;

const TICK_MS = 1000;

type Phase = "countdown" | "blocked" | "copy-failed";

/**
 * Starts the clipboard write. MUST be called synchronously inside the click handler (user
 * activation) and its promise handed to `ChatGptLaunchDialog` as `copying`.
 */
export function copyPromptToClipboard(prompt: string): Promise<void> {
  if (!navigator.clipboard) return Promise.reject(new Error("Clipboard API unavailable"));
  return navigator.clipboard.writeText(prompt);
}

interface ChatGptLaunchDialogProps {
  prompt: string;
  /** Result of `copyPromptToClipboard(prompt)` started in the click. Mount the dialog only while open. */
  copying: Promise<void>;
  onClose: () => void;
}

/**
 * "Montar com o ChatGPT" launch flow (decision 2026-11-06): the prompt is already on the
 * clipboard, a short countdown tells the user what to do, then chatgpt.com opens in another window.
 * Closing the dialog (X / outside) cancels the countdown because the effects unmount with it.
 */
export function ChatGptLaunchDialog({ prompt, copying, onClose }: ChatGptLaunchDialogProps) {
  const [phase, setPhase] = useState<Phase>("countdown");
  const [copied, setCopied] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(CHATGPT_OPEN_DELAY_SECONDS);

  useEffect(() => {
    let cancelled = false;
    copying.then(
      () => !cancelled && setCopied(true),
      () => !cancelled && setPhase("copy-failed")
    );
    return () => {
      cancelled = true;
    };
  }, [copying]);

  const counting = copied && phase === "countdown";

  useEffect(() => {
    if (!counting) return;
    const timer = setInterval(() => setSecondsLeft((seconds) => seconds - 1), TICK_MS);
    return () => clearInterval(timer);
  }, [counting]);

  const openChatGpt = () => {
    // No "noopener" in the features: per spec it makes window.open return null, hiding a blocked popup.
    const opened = window.open(CHATGPT_URL, "_blank");
    if (!opened) return setPhase("blocked");
    opened.opener = null;
    onClose();
  };

  useEffect(() => {
    if (counting && secondsLeft <= 0) openChatGpt();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fires once when the countdown ends
  }, [counting, secondsLeft]);

  const retryCopy = () => {
    copyPromptToClipboard(prompt).then(
      () => {
        setSecondsLeft(CHATGPT_OPEN_DELAY_SECONDS);
        setPhase("countdown");
        setCopied(true);
      },
      () => undefined
    );
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {phase === "copy-failed" ? "Não consegui copiar automaticamente" : "Prompt copiado"}
          </DialogTitle>
          <DialogDescription className="text-sm">{describe(phase)}</DialogDescription>
        </DialogHeader>

        {counting && (
          <div className="space-y-2" aria-live="polite">
            <p className="text-sm font-medium tabular-nums">
              Abrindo o ChatGPT em {Math.max(secondsLeft, 0)} s
            </p>
            <Progress
              value={
                ((CHATGPT_OPEN_DELAY_SECONDS - secondsLeft) / CHATGPT_OPEN_DELAY_SECONDS) * 100
              }
            />
          </div>
        )}

        {phase === "copy-failed" && (
          <pre className="bg-muted/40 max-h-64 overflow-y-auto rounded-md border p-3 text-xs break-all whitespace-pre-wrap">
            {prompt}
          </pre>
        )}

        <DialogFooter>
          {phase === "copy-failed" ? (
            <Button type="button" className="max-md:h-11" onClick={retryCopy}>
              <Copy />
              Copiar de novo
            </Button>
          ) : (
            <Button type="button" className="max-md:h-11" onClick={openChatGpt}>
              <ExternalLink />
              {phase === "blocked" ? "Abrir o ChatGPT" : "Abrir agora"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function describe(phase: Phase): string {
  if (phase === "blocked")
    return "O navegador bloqueou a janela. Toque no botão para abrir o ChatGPT.";
  if (phase === "copy-failed")
    return "Selecione o texto abaixo, copie e cole no ChatGPT. Ou toque em Copiar de novo.";
  return `Em ${CHATGPT_OPEN_DELAY_SECONDS} s abrimos o ChatGPT em outra janela. No computador, clique na caixa de mensagem e cole com Ctrl+V (⌘+V no Mac). No celular, toque e segure na caixa e escolha Colar. Depois é só enviar.`;
}
