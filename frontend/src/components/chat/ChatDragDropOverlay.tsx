import { cn } from "@/lib/utils";
import { Ban, UploadCloud } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatRejectionEntry } from "./rejection-types";

interface ChatDragDropOverlayProps {
  accept: string | undefined;
  modelName: string | undefined;
  onReject: (entries: ChatRejectionEntry[]) => void;
}

function parseAcceptPatterns(accept: string | undefined): string[] {
  if (!accept) return [];
  return accept
    .split(",")
    .map((t) => t.trim().toLowerCase())
    .filter(Boolean);
}

function matchesPattern(mediaType: string, filename: string, pattern: string): boolean {
  const mt = mediaType.toLowerCase();
  if (pattern.startsWith(".")) {
    return filename.toLowerCase().endsWith(pattern);
  }
  if (pattern.endsWith("/*")) {
    const prefix = pattern.slice(0, -1);
    return mt.startsWith(prefix);
  }
  return mt === pattern;
}

function isAccepted(mediaType: string, filename: string, patterns: string[]): boolean {
  if (patterns.length === 0) return true;
  return patterns.some((p) => matchesPattern(mediaType, filename, p));
}

/** Optimistic check used DURING drag — we only have mime, not filename. */
function isLikelyAcceptedDuringDrag(mediaType: string, patterns: string[]): boolean {
  if (patterns.length === 0) return true;
  const mt = mediaType.toLowerCase();
  if (mt.startsWith("image/")) return patterns.some((p) => p === "image/*" || p === mt);
  if (mt.startsWith("audio/")) return patterns.some((p) => p === "audio/*" || p === mt);
  if (mt.startsWith("video/")) return patterns.some((p) => p === "video/*" || p === mt);
  return true;
}

function reasonForMime(mediaType: string): ChatRejectionEntry["reason"] {
  if (mediaType.startsWith("image/")) return "image_not_supported";
  if (mediaType.startsWith("audio/")) return "audio_not_supported";
  if (mediaType.startsWith("video/")) return "video_not_supported";
  return "unsupported_type";
}

export function ChatDragDropOverlay({ accept, modelName, onReject }: ChatDragDropOverlayProps) {
  const [active, setActive] = useState(false);
  const [hasInvalid, setHasInvalid] = useState(false);
  const dragDepthRef = useRef(0);

  const patterns = parseAcceptPatterns(accept);
  const patternsRef = useRef(patterns);
  patternsRef.current = patterns;

  const reset = useCallback(() => {
    dragDepthRef.current = 0;
    setActive(false);
    setHasInvalid(false);
  }, []);

  useEffect(() => {
    function inspectItems(items: DataTransferItemList | null): { invalid: boolean } {
      if (!items) return { invalid: false };
      let invalid = false;
      for (const it of items) {
        if (it.kind !== "file") continue;
        const mime = (it.type || "").toLowerCase();
        if (!isLikelyAcceptedDuringDrag(mime, patternsRef.current)) {
          invalid = true;
        }
      }
      return { invalid };
    }

    function onDragEnter(event: DragEvent) {
      const dt = event.dataTransfer;
      if (!dt) return;
      const hasFile = Array.from(dt.types || []).includes("Files");
      if (!hasFile) return;
      dragDepthRef.current += 1;
      const { invalid } = inspectItems(dt.items);
      setActive(true);
      setHasInvalid(invalid);
    }

    function onDragOver(event: DragEvent) {
      const dt = event.dataTransfer;
      if (!dt) return;
      const hasFile = Array.from(dt.types || []).includes("Files");
      if (!hasFile) return;
      event.preventDefault();
    }

    function onDragLeave() {
      dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
      if (dragDepthRef.current === 0) {
        setActive(false);
        setHasInvalid(false);
      }
    }

    function onDrop(event: DragEvent) {
      const dt = event.dataTransfer;
      if (!dt || !dt.files || dt.files.length === 0) {
        reset();
        return;
      }
      const rejected: ChatRejectionEntry[] = [];
      for (const file of Array.from(dt.files)) {
        const mime = (file.type || "application/octet-stream").toLowerCase();
        if (!isAccepted(mime, file.name, patternsRef.current)) {
          rejected.push({
            filename: file.name,
            mediaType: mime,
            reason: reasonForMime(mime),
          });
        }
      }
      if (rejected.length > 0) {
        event.preventDefault();
        event.stopPropagation();
        onReject(rejected);
      }
      reset();
    }

    document.addEventListener("dragenter", onDragEnter);
    document.addEventListener("dragover", onDragOver);
    document.addEventListener("dragleave", onDragLeave);
    document.addEventListener("drop", onDrop, true);
    return () => {
      document.removeEventListener("dragenter", onDragEnter);
      document.removeEventListener("dragover", onDragOver);
      document.removeEventListener("dragleave", onDragLeave);
      document.removeEventListener("drop", onDrop, true);
    };
  }, [onReject, reset]);

  if (!active) return null;

  const Icon = hasInvalid ? Ban : UploadCloud;
  const headline = hasInvalid ? "Unsupported file type" : "Drop to attach";
  const detail = hasInvalid
    ? `${modelName ?? "This model"} only accepts the configured compatible formats.`
    : "Release the files anywhere on the window.";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.12 }}
      className="bg-background/70 pointer-events-none fixed inset-0 z-50 flex items-center justify-center backdrop-blur-sm"
      aria-hidden
    >
      <div
        className={cn(
          "flex flex-col items-center gap-3 rounded-3xl border-2 border-dashed px-10 py-12 shadow-lg",
          "bg-background/90",
          hasInvalid ? "border-destructive/60 text-destructive" : "border-primary/60 text-primary"
        )}
      >
        <Icon className="size-10" />
        <p className="text-lg font-semibold">{headline}</p>
        <p className="text-muted-foreground max-w-md text-center text-sm">{detail}</p>
      </div>
    </motion.div>
  );
}
