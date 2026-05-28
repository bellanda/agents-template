import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { ExternalLinkIcon } from "lucide-react";

interface ChatImageLightboxProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  url: string;
  filename: string;
}

export function ChatImageLightbox({ open, onOpenChange, url, filename }: ChatImageLightboxProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="max-w-[95vw] gap-0 overflow-hidden border-none bg-transparent p-0 shadow-none sm:max-w-[95vw]"
      >
        <DialogTitle className="sr-only">{filename || "Attachment"}</DialogTitle>
        <div className="flex flex-col items-center gap-3">
          <img
            src={url}
            alt={filename || "Attachment"}
            className="max-h-[85vh] max-w-[95vw] rounded-lg object-contain shadow-2xl"
          />
          <Button asChild variant="secondary" size="sm" className="gap-2">
            <a href={url} target="_blank" rel="noreferrer">
              <ExternalLinkIcon className="size-4" />
              Open original
            </a>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
