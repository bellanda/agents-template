import {
  Message,
  MessageAction,
  MessageActions,
  MessageContent,
  MessageResponse,
  MessageToolbar,
} from "@/components/ai-elements/message";
import { Reasoning, ReasoningContent, ReasoningTrigger } from "@/components/ai-elements/reasoning";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import { ChatImageLightbox } from "@/components/chat/ChatImageLightbox";
import { cn } from "@/lib/utils";
import type { UIMessage } from "ai";
import { CheckIcon, CopyIcon, FileTextIcon } from "lucide-react";
import { motion } from "motion/react";
import { memo, useCallback, useState } from "react";

const COPY_TIMEOUT_MS = 2000;

interface ToolPart {
  state:
    | "input-streaming"
    | "input-available"
    | "approval-requested"
    | "approval-responded"
    | "output-available"
    | "output-error"
    | "output-denied";
  toolName: string;
  toolCallId: string;
  input?: unknown;
  output?: unknown;
  errorText?: string;
}

function extractUserText(msg: UIMessage): string {
  if (!Array.isArray(msg.parts)) return "";
  return (
    msg.parts
      .filter((p) => p?.type === "text")
      .map((p) => String((p as unknown as { text?: string }).text ?? ""))
      .filter(Boolean)
      .join(" ")
      .trim() || ""
  );
}

const CopyAction = memo(({ content }: { content: string }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), COPY_TIMEOUT_MS);
  }, [content]);

  return (
    <MessageAction
      label="Copy"
      onClick={handleCopy}
      tooltip={copied ? "Copied!" : "Copy to clipboard"}
    >
      {copied ? <CheckIcon className="size-4" /> : <CopyIcon className="size-4" />}
    </MessageAction>
  );
});
CopyAction.displayName = "CopyAction";

interface FilePart {
  type: "file";
  url: string;
  mediaType?: string;
  filename?: string;
}

function formatFileSize(bytes: number | undefined): string {
  if (!bytes || bytes <= 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface FileAttachmentProps {
  url: string;
  filename: string;
  mediaType: string;
  size?: number;
}

function FileImageAttachment({ url, filename, mediaType }: FileAttachmentProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="border-border/60 hover:border-border focus-visible:ring-ring/50 group/file relative block overflow-hidden rounded-xl border focus-visible:ring-2 focus-visible:outline-none"
      >
        <img
          src={url}
          alt={filename || "Attachment"}
          className="bg-muted max-h-72 max-w-full object-contain"
          loading="lazy"
        />
      </button>
      <ChatImageLightbox
        open={open}
        onOpenChange={setOpen}
        url={url}
        filename={filename || mediaType}
      />
    </>
  );
}

function FileDocumentAttachment({ url, filename, mediaType, size }: FileAttachmentProps) {
  const sizeLabel = formatFileSize(size);
  const subtitle = sizeLabel ? `${mediaType || "file"} · ${sizeLabel}` : mediaType || "file";
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="border-border/70 hover:border-border bg-muted/40 hover:bg-muted/70 flex max-w-md items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors"
    >
      <div className="bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-lg">
        <FileTextIcon className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{filename || "File"}</p>
        <p className="text-muted-foreground truncate text-xs">{subtitle}</p>
      </div>
    </a>
  );
}

interface ChatMessageProps {
  message: UIMessage;
  isLastMessage: boolean;
  isStreaming: boolean;
}

function ChatMessageBase({ message, isLastMessage, isStreaming }: ChatMessageProps) {
  const isAssistant = message.role === "assistant";
  const sortedParts = message.parts ?? [];

  const hasTextPart = sortedParts.some(
    (p) => p?.type === "text" && Boolean((p as { text?: string }).text)
  );
  const isReasoningStreaming = isLastMessage && isStreaming && !hasTextPart;

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
    >
      <Message
        from={message.role}
        className={cn(
          "group transition-colors",
          isAssistant && "mx-auto max-w-full !border-l-0 !pl-0",
          !isAssistant && "max-w-[80%]"
        )}
      >
        <MessageContent className={cn(isAssistant && "w-full max-w-full overflow-visible")}>
          {sortedParts.map((part, i) => {
            if (!part || typeof part !== "object") return null;
            const textContent = (part as { text?: string }).text || "";
            const isToolPart = part.type === "dynamic-tool";
            const widthClass = isToolPart ? "w-full" : "w-full max-w-3xl";

            if (part.type === "reasoning") {
              const reasoningText =
                (part as { reasoning?: string }).reasoning ||
                (part as { text?: string }).text ||
                "";
              const shouldShowReasoning =
                (isAssistant && (isReasoningStreaming || reasoningText)) || reasoningText;
              if (!shouldShowReasoning) return null;
              return (
                <div key={`${message.id}-reasoning-${i}`} className={widthClass}>
                  <Reasoning isStreaming={isReasoningStreaming}>
                    <ReasoningTrigger />
                    <ReasoningContent>{reasoningText}</ReasoningContent>
                  </Reasoning>
                </div>
              );
            }

            if (part.type === "text") {
              return (
                <div key={`${message.id}-text-${i}`} className={widthClass}>
                  <MessageResponse>{textContent}</MessageResponse>
                </div>
              );
            }

            if (part.type === "file") {
              const filePart = part as FilePart & { size?: number };
              const url = filePart.url || "";
              if (!url) return null;
              const mediaType = filePart.mediaType || "";
              const filename = filePart.filename || "";
              const isImage = mediaType.startsWith("image/");
              const key = `${message.id}-file-${i}`;
              return (
                <div key={key} className={widthClass}>
                  {isImage ? (
                    <FileImageAttachment
                      url={url}
                      filename={filename}
                      mediaType={mediaType}
                      size={filePart.size}
                    />
                  ) : (
                    <FileDocumentAttachment
                      url={url}
                      filename={filename}
                      mediaType={mediaType}
                      size={filePart.size}
                    />
                  )}
                </div>
              );
            }

            if (part.type === "dynamic-tool") {
              const toolPart = part as ToolPart;
              const key = `${message.id}-tool-${toolPart.toolCallId}`;

              return (
                <div key={key} className="w-full">
                  <Tool defaultOpen={false}>
                    <ToolHeader
                      type="dynamic-tool"
                      state={toolPart.state}
                      toolName={toolPart.toolName}
                    />
                    <ToolContent>
                      <ToolInput input={toolPart.input} />
                      {(toolPart.state === "output-available" ||
                        toolPart.state === "output-error") && (
                        <ToolOutput output={toolPart.output} errorText={toolPart.errorText} />
                      )}
                    </ToolContent>
                  </Tool>
                </div>
              );
            }

            return null;
          })}
          {isAssistant && sortedParts.length === 0 && (
            <div className="w-full max-w-3xl">
              <MessageResponse>{extractUserText(message)}</MessageResponse>
            </div>
          )}
        </MessageContent>

        {isAssistant && (
          <MessageToolbar className="opacity-0 transition-opacity group-hover:opacity-100">
            <MessageActions>
              <CopyAction content={extractUserText(message)} />
            </MessageActions>
          </MessageToolbar>
        )}
      </Message>
    </motion.div>
  );
}

export const ChatMessage = memo(ChatMessageBase, (prev, next) => {
  if (prev.message !== next.message) return false;
  if (prev.isLastMessage !== next.isLastMessage) return false;
  if (prev.isLastMessage && prev.isStreaming !== next.isStreaming) return false;
  return true;
});
ChatMessage.displayName = "ChatMessage";
