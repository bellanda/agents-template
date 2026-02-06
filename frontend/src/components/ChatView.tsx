import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useChat } from "@ai-sdk/react";
import type { UIMessage } from "ai";
import { DefaultChatTransport } from "ai";
import { ArrowDown, Brain, SendHorizonal, Square } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { Streamdown } from "streamdown";

// ── Types ──────────────────────────────────────────────────────────────────────

interface ChatViewProps {
  agentId: string;
  sessionId?: string;
  singleShot?: boolean;
}

// ── Main Component ─────────────────────────────────────────────────────────────

export function ChatView({ agentId, sessionId, singleShot = false }: ChatViewProps) {
  const [reasoningOpenMap, setReasoningOpenMap] = useState<Record<string, boolean>>({});
  const [input, setInput] = useState("");
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { messages, sendMessage, setMessages, status, stop } = useChat({
    transport: new DefaultChatTransport({
      api: "/api/v1/agents/chat/completions",
      body: {
        model: agentId,
        stream: true,
        ...(sessionId ? { session_id: sessionId } : {})
      }
    })
  });

  const isStreaming = status === "submitted" || status === "streaming";

  function scrollToBottom() {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }

  // Auto-scroll during streaming
  useLayoutEffect(() => {
    if (isStreaming) {
      scrollToBottom();
    }
  }, [messages, isStreaming]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    if (singleShot) {
      setMessages([]);
      setReasoningOpenMap({});
    }

    sendMessage({ text: input });
    setInput("");
    textareaRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div ref={scrollAreaRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
            <p className="text-lg font-medium">{singleShot ? "Ask anything" : "Start a conversation"}</p>
            <p className="text-sm">
              {singleShot
                ? "Each request is independent - no conversation history"
                : "Your messages are saved and the conversation will persist"}
            </p>
          </div>
        )}

        {messages.map((message, idx) => {
          const isLast = idx === messages.length - 1;
          const isAssistant = message.role === "assistant";

          // Sort parts: reasoning first, then text
          const sortedParts = [...(message.parts ?? [])].sort((a, b) => {
            const order: Record<string, number> = { reasoning: 0, text: 1 };
            return (order[a?.type] ?? 2) - (order[b?.type] ?? 2);
          });

          const hasTextPart = sortedParts.some((p) => p?.type === "text");

          return (
            <div key={message.id} className={cn("flex gap-3", isAssistant ? "justify-start" : "justify-end")}>
              <div
                className={cn(
                  "max-w-[80%] rounded-lg px-4 py-3",
                  isAssistant ? "text-foreground" : "bg-primary text-primary-foreground"
                )}
              >
                {isAssistant ? (
                  sortedParts.map((part, i) => {
                    if (!part || typeof part !== "object") return null;

                    const textContent = "text" in part ? String((part as unknown as { text?: string }).text ?? "") : "";

                    switch (part.type) {
                      case "reasoning": {
                        const isReasoningStreaming = isStreaming && isLast && !hasTextPart;
                        const isOpen = reasoningOpenMap[message.id] ?? (hasTextPart ? false : true);

                        return (
                          <ReasoningBlock
                            key={`${message.id}-${i}`}
                            content={textContent}
                            isStreaming={isReasoningStreaming}
                            open={isOpen}
                            onOpenChange={(open) =>
                              setReasoningOpenMap((prev) => ({
                                ...prev,
                                [message.id]: open
                              }))
                            }
                          />
                        );
                      }
                      case "text":
                        return (
                          <Streamdown
                            key={`${message.id}-${i}`}
                            className="prose prose-sm dark:prose-invert max-w-none wrap-break-word [&_a]:cursor-pointer [&_pre]:overflow-x-auto [&_pre]:max-w-full [&_code]:break-all"
                            parseIncompleteMarkdown
                          >
                            {textContent}
                          </Streamdown>
                        );
                      default:
                        return null;
                    }
                  })
                ) : (
                  <p className="whitespace-pre-wrap wrap-break-word">{extractUserText(message)}</p>
                )}
              </div>
            </div>
          );
        })}

        {isStreaming && messages.length > 0 && (
          <div className="flex justify-center">
            <Button variant="outline" size="sm" onClick={stop}>
              <Square className="size-4 mr-1" />
              Stop
            </Button>
          </div>
        )}
      </div>

      {/* Scroll to bottom */}
      {messages.length > 3 && (
        <div className="flex justify-center -mt-12 relative z-10">
          <Button variant="outline" size="icon" className="rounded-full shadow-lg size-8" onClick={scrollToBottom}>
            <ArrowDown className="size-4" />
          </Button>
        </div>
      )}

      {/* Input area */}
      <form onSubmit={handleSubmit} className="border-t p-4 flex gap-2 items-end">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message..."
          rows={1}
          className="flex-1 resize-none rounded-lg border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[40px] max-h-[120px]"
          style={{
            height: "auto",
            minHeight: "40px"
          }}
          onInput={(e) => {
            const target = e.target as HTMLTextAreaElement;
            target.style.height = "auto";
            target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
          }}
        />
        <Button type="submit" size="icon" disabled={!input.trim() || isStreaming}>
          <SendHorizonal className="size-4" />
        </Button>
      </form>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────────

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

// ── Reasoning Block ────────────────────────────────────────────────────────────

function ReasoningBlock({
  content,
  isStreaming,
  open,
  onOpenChange
}: {
  content: string;
  isStreaming: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (isStreaming && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [content, isStreaming]);

  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => onOpenChange(!open)}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <Brain className="size-3.5 shrink-0" />
        <span className={cn("transition-transform", open && "rotate-90")}>▸</span>
        {isStreaming ? <span className="animate-pulse">Thinking...</span> : <span>Reasoning</span>}
      </button>
      {open && (
        <div
          ref={scrollRef}
          className="mt-1 max-h-48 overflow-y-auto text-xs text-muted-foreground bg-muted/50 rounded p-2 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
        >
          <pre className="whitespace-pre-wrap font-mono">{content}</pre>
        </div>
      )}
    </div>
  );
}
