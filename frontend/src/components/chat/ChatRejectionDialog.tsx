import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FileWarning } from "lucide-react";
import type { ChatRejection } from "./rejection-types";

interface ChatRejectionDialogProps {
  rejection: ChatRejection | null;
  onClose: () => void;
  onSwitchModel?: () => void;
}

function reasonLabel(reason: ChatRejection["entries"][number]["reason"]): string {
  switch (reason) {
    case "image_not_supported":
      return "this model does not accept images";
    case "audio_not_supported":
      return "this model does not accept audio";
    case "video_not_supported":
      return "this model does not accept video";
    case "too_large":
      return "file exceeds the maximum size";
    case "unsupported_type":
      return "unsupported file type";
    case "max_files":
      return "too many files selected";
    case "thread_files_full":
      return "per-conversation file limit reached";
    case "thread_images_full":
      return "per-conversation image limit reached";
    case "thread_documents_full":
      return "per-conversation document limit reached";
    case "user_files_full":
      return "total user file limit reached";
    case "user_storage_full":
      return "storage quota exhausted";
    case "network":
      return "network error";
    default:
      return "attachment rejected";
  }
}

export function ChatRejectionDialog({
  rejection,
  onClose,
  onSwitchModel,
}: ChatRejectionDialogProps) {
  const open = rejection !== null;
  const showSwitch =
    Boolean(onSwitchModel) &&
    rejection !== null &&
    rejection.entries.some(
      (e) =>
        e.reason === "image_not_supported" ||
        e.reason === "audio_not_supported" ||
        e.reason === "video_not_supported"
    );

  return (
    <Dialog open={open} onOpenChange={(next) => (!next ? onClose() : undefined)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader className="space-y-2 text-left">
          <DialogTitle className="flex items-center gap-2">
            <FileWarning className="text-destructive size-5" aria-hidden />
            <span>Attachment not supported</span>
          </DialogTitle>
          {rejection?.modelName && (
            <DialogDescription>
              <span className="text-foreground font-medium">{rejection.modelName}</span> couldn't
              accept {rejection.entries.length === 1 ? "this attachment" : "these attachments"}.
            </DialogDescription>
          )}
        </DialogHeader>

        {rejection && rejection.entries.length > 0 && (
          <ul className="border-border/60 divide-border/60 max-h-60 divide-y overflow-y-auto rounded-md border text-sm">
            {rejection.entries.map((entry, i) => (
              <li key={`${entry.filename}-${i}`} className="flex flex-col gap-0.5 px-3 py-2">
                <span className="text-foreground truncate font-medium" title={entry.filename}>
                  {entry.filename}
                </span>
                <span className="text-muted-foreground text-xs">
                  {entry.mediaType || "unknown type"} — {reasonLabel(entry.reason)}
                </span>
              </li>
            ))}
          </ul>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="outline" onClick={onClose}>
            Got it
          </Button>
          {showSwitch && (
            <Button
              type="button"
              onClick={() => {
                onSwitchModel?.();
                onClose();
              }}
            >
              Switch model
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
