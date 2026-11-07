import { CHATGPT_URL } from "@/components/agent-config/chatgpt-builder-prompt";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { Copy, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";

/**
 * Seconds between "prompt copied" and opening chatgpt.com (user, 2026-11-07: "Pode ser 4s").
 * `window.open` outside a click handler only works while the click's transient user activation
 * lasts — 5 s in Chrome and Firefox, less in Safari/iOS — so do NOT raise this above 4. If the
 * browser blocks it anyway the counter gives way to a button (a real gesture).
 */
export const CHATGPT_OPEN_DELAY_SECONDS = 4;

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
 * "Montar com o ChatGPT" launch flow (decision 2026-11-06, layout 2026-11-07): the prompt is
 * already on the clipboard; the dialog shows ONLY two big sentences ("Prompt copiado!" in green +
 * "Cole o conteúdo no ChatGPT (Ctrl + V)") and the countdown, then chatgpt.com opens in another
 * window. User 2026-11-07: "somente 2 frases e em baixo somente o contador nada mais" — no "open
 * now" button; a button only appears when the browser blocks the window or the copy fails.
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

  const copyFailed = phase === "copy-failed";

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="gap-8 p-8 sm:max-w-2xl sm:gap-10 sm:p-12">
        <DialogHeader className="items-center gap-3 text-center sm:text-center">
          <DialogTitle
            className={cn(
              "text-3xl font-bold sm:text-5xl",
              copyFailed ? "text-destructive" : "text-emerald-600 dark:text-emerald-400"
            )}
          >
            {copyFailed ? "Não consegui copiar" : "Prompt copiado!"}
          </DialogTitle>
          <DialogDescription className="text-foreground text-xl font-medium sm:text-3xl">
            {copyFailed ? (
              "Copie o texto abaixo e cole no ChatGPT"
            ) : (
              <>
                Cole o conteúdo no ChatGPT{" "}
                {/* Ctrl + V means nothing on a phone: there the sentence alone is the instruction. */}
                <span className="whitespace-nowrap pointer-coarse:hidden">(Ctrl + V)</span>
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        {counting && <OpeningCountdown secondsLeft={secondsLeft} />}

        {phase === "blocked" && (
          <Button type="button" className="mx-auto h-12 px-6 text-base" onClick={openChatGpt}>
            <ExternalLink />
            Abrir o ChatGPT
          </Button>
        )}

        {copyFailed && (
          <>
            <pre className="bg-muted/40 max-h-64 overflow-y-auto rounded-md border p-3 text-left text-xs break-all whitespace-pre-wrap">
              {prompt}
            </pre>
            <Button type="button" className="mx-auto h-12 px-6 text-base" onClick={retryCopy}>
              <Copy />
              Copiar de novo
            </Button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Big seconds number + bar. `role="timer"` stays silent for screen readers (aria-live off). */
function OpeningCountdown({ secondsLeft }: { secondsLeft: number }) {
  const seconds = Math.max(secondsLeft, 0);
  const elapsedPercent =
    ((CHATGPT_OPEN_DELAY_SECONDS - seconds) / CHATGPT_OPEN_DELAY_SECONDS) * 100;
  return (
    <div
      role="timer"
      aria-label={`Abrindo o ChatGPT em ${seconds} s`}
      className="mx-auto flex w-full max-w-xs flex-col items-center gap-3"
    >
      <span className="text-7xl leading-none font-bold tabular-nums sm:text-8xl">{seconds}</span>
      <Progress value={elapsedPercent} className="h-2" />
    </div>
  );
}
