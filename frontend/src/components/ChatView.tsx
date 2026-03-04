"use client";

import {
  Attachment,
  AttachmentPreview,
  AttachmentRemove,
  Attachments,
  type AttachmentData
} from "@/components/ai-elements/attachments";
import { Conversation, ConversationContent, ConversationEmptyState } from "@/components/ai-elements/conversation";
import {
  Message,
  MessageAction,
  MessageActions,
  MessageContent,
  MessageResponse,
  MessageToolbar
} from "@/components/ai-elements/message";
import {
  ModelSelector,
  ModelSelectorContent,
  ModelSelectorEmpty,
  ModelSelectorGroup,
  ModelSelectorInput,
  ModelSelectorItem,
  ModelSelectorList,
  ModelSelectorLogo,
  ModelSelectorLogoGroup,
  ModelSelectorName,
  ModelSelectorTrigger
} from "@/components/ai-elements/model-selector";
import {
  PromptInput,
  PromptInputActionAddAttachments,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuTrigger,
  PromptInputBody,
  PromptInputButton,
  PromptInputFooter,
  PromptInputProvider,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  usePromptInputAttachments,
  type PromptInputMessage
} from "@/components/ai-elements/prompt-input";
import { Reasoning, ReasoningContent, ReasoningTrigger } from "@/components/ai-elements/reasoning";
import { Suggestion, Suggestions } from "@/components/ai-elements/suggestion";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useUserId } from "@/hooks/useUserId";
import { fetchAgents, fetchThreadMessages, type AgentModel } from "@/lib/api";
import { getCachedMessages, invalidateThread, setCachedMessages, toUIMessages } from "@/lib/thread-messages-cache";
import { useChat } from "@ai-sdk/react";
import { useNavigate } from "@tanstack/react-router";
import type { UIMessage } from "ai";
import { DefaultChatTransport } from "ai";
import { ArrowDownIcon, CheckIcon, CopyIcon, GlobeIcon, MessageSquareIcon } from "lucide-react";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

// ── Types ──────────────────────────────────────────────────────────────────────

interface ChatViewProps {
  agentId: string;
  sessionId?: string;
  singleShot?: boolean;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const enrichAgent = (agent: AgentModel): AgentModel => {
  const id = agent.id.toLowerCase();
  const desc = agent.description?.toLowerCase() || "";

  let chef = "Custom";
  let chefSlug = "zai";
  let providers: string[] = [];

  if (id.includes("gpt") || desc.includes("openai")) {
    chef = "OpenAI";
    chefSlug = "openai";
  } else if (id.includes("claude") || desc.includes("anthropic")) {
    chef = "Anthropic";
    chefSlug = "anthropic";
  } else if (id.includes("gemini") || desc.includes("google")) {
    chef = "Google";
    chefSlug = "google";
  } else if (id.includes("deepseek") || desc.includes("deepseek")) {
    chef = "DeepSeek";
    chefSlug = "deepseek";
  } else if (id.includes("qwen") || desc.includes("qwen")) {
    chef = "Alibaba";
    chefSlug = "alibaba";
  } else if (id.includes("kimi") || desc.includes("moonshot")) {
    chef = "Moonshot";
    chefSlug = "moonshotai";
  } else if (id.includes("minimax") || desc.includes("minimax")) {
    chef = "MiniMax";
    chefSlug = "zai"; // generic
  }

  // Detect providers from description
  if (desc.includes("chutes")) providers.push("chutes");
  if (desc.includes("groq")) providers.push("groq");
  if (desc.includes("google")) providers.push("google");
  if (desc.includes("nvidia")) providers.push("nvidia");
  if (desc.includes("cerebras")) providers.push("cerebras");

  return { ...agent, chef, chefSlug, providers };
};

// ── Model Item Component ───────────────────────────────────────────────────────

interface ModelItemProps {
  agent: AgentModel;
  selectedAgentId: string;
  onSelect: (id: string) => void;
}

const ModelItem = memo(({ agent, selectedAgentId, onSelect }: ModelItemProps) => {
  const handleSelect = useCallback(() => {
    onSelect(agent.id);
  }, [onSelect, agent.id]);

  const enriched = useMemo(() => enrichAgent(agent), [agent]);

  return (
    <ModelSelectorItem key={agent.id} onSelect={handleSelect} value={agent.id}>
      {enriched.chefSlug && <ModelSelectorLogo provider={enriched.chefSlug} />}
      <ModelSelectorName>{agent.name}</ModelSelectorName>
      {enriched.providers && enriched.providers.length > 0 && (
        <ModelSelectorLogoGroup>
          {enriched.providers.map((p) => (
            <ModelSelectorLogo key={p} provider={p} />
          ))}
        </ModelSelectorLogoGroup>
      )}
      {selectedAgentId === agent.id ? <CheckIcon className="ml-auto size-4" /> : <div className="ml-auto size-4" />}
    </ModelSelectorItem>
  );
});

ModelItem.displayName = "ModelItem";

// ── Message Actions ──────────────────────────────────────────────────────────

const CopyAction = memo(({ content }: { content: string }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [content]);

  return (
    <MessageAction label="Copy" onClick={handleCopy} tooltip={copied ? "Copied!" : "Copy to clipboard"}>
      {copied ? <CheckIcon className="size-4" /> : <CopyIcon className="size-4" />}
    </MessageAction>
  );
});
CopyAction.displayName = "CopyAction";

// ── Attachment Item Component ──────────────────────────────────────────────────

interface AttachmentItemProps {
  attachment: { id: string; filename?: string; mediaType?: string; url: string; type: "file" };
  onRemove?: (id: string) => void;
}

const AttachmentItem = memo(({ attachment, onRemove }: AttachmentItemProps) => {
  const handleRemove = useCallback(() => {
    onRemove?.(attachment.id);
  }, [onRemove, attachment.id]);

  return (
    <Attachment data={attachment as AttachmentData} onRemove={onRemove ? handleRemove : undefined}>
      <AttachmentPreview />
      {onRemove && <AttachmentRemove />}
    </Attachment>
  );
});

AttachmentItem.displayName = "AttachmentItem";

// ── Prompt Input Attachments Display ───────────────────────────────────────────

const PromptInputAttachmentsDisplay = () => {
  const attachments = usePromptInputAttachments();

  const handleRemove = useCallback(
    (id: string) => {
      attachments.remove(id);
    },
    [attachments]
  );

  if (attachments.files.length === 0) {
    return null;
  }

  return (
    <Attachments variant="inline">
      {attachments.files.map((attachment) => (
        <AttachmentItem
          attachment={{
            id: attachment.id,
            filename: attachment.filename || "File",
            mediaType: attachment.mediaType ?? "application/octet-stream",
            url: attachment.url || "",
            type: "file"
          }}
          key={attachment.id}
          onRemove={handleRemove}
        />
      ))}
    </Attachments>
  );
};

// ── Main Component ─────────────────────────────────────────────────────────────

export function ChatView({ agentId, sessionId, singleShot = false }: ChatViewProps) {
  const [userId] = useUserId();
  const navigate = useNavigate();
  const [selectedAgentId, setSelectedAgentId] = useState(agentId);
  const selectedAgentIdRef = useRef(agentId);
  const [agents, setAgents] = useState<AgentModel[]>([]);
  const [modelSelectorOpen, setModelSelectorOpen] = useState(false);
  const [isHydrating, setIsHydrating] = useState(false);
  const inputRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const [inputHeight, setInputHeight] = useState(200);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const isUserScrollingRef = useRef(false);

  // Load agents for selector
  useEffect(() => {
    fetchAgents().then(setAgents).catch(console.error);
  }, []);

  // Sync agentId prop with selectedAgentId state and save to localStorage
  useEffect(() => {
    setSelectedAgentId(agentId);
    selectedAgentIdRef.current = agentId;
    // Save agent from URL/prop to localStorage (for threads, this is the agent used in that conversation)
    localStorage.setItem("lastSelectedAgentId", agentId);
  }, [agentId]);

  const selectedAgent = useMemo(() => {
    const agent = agents.find((a) => a.id === selectedAgentId);
    return agent ? enrichAgent(agent) : undefined;
  }, [agents, selectedAgentId]);

  const chatAgents = useMemo(() => agents.filter((a) => a.save_to_db).map(enrichAgent), [agents]);

  const agentsByChef = useMemo(() => {
    const groups: Record<string, AgentModel[]> = {};
    chatAgents.forEach((agent) => {
      const chef = agent.chef || "Custom";
      if (!groups[chef]) groups[chef] = [];
      groups[chef].push(agent);
    });
    return groups;
  }, [chatAgents]);

  // Memoize transport to prevent unnecessary re-renders
  // Use a function for body to ensure it always uses the latest selectedAgentId from ref
  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: "/api/v1/agents/chat/completions",
        body: () => ({
          model: selectedAgentIdRef.current,
          stream: true,
          user: userId,
          ...(sessionId ? { session_id: sessionId } : {})
        })
      }),
    [userId, sessionId]
  );

  const {
    messages: rawMessages,
    sendMessage,
    setMessages,
    status,
    stop
  } = useChat({
    id: sessionId,
    transport,
    onFinish() {
      if (sessionId) invalidateThread(sessionId);
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent("agents:threads:updated"));
      }, 500);
    }
  });

  // Debounced messages state to reduce re-renders during streaming
  const [messages, setMessagesState] = useState<UIMessage[]>(rawMessages);
  const messagesBufferRef = useRef<UIMessage[]>(rawMessages);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const prevIsStreamingRef = useRef(false);

  // Update buffer immediately when rawMessages change
  useEffect(() => {
    const isStreaming = status === "submitted" || status === "streaming";
    const wasStreaming = prevIsStreamingRef.current;
    prevIsStreamingRef.current = isStreaming;

    // Always update buffer with latest messages
    messagesBufferRef.current = rawMessages;

    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    // If streaming, debounce updates (3ms) to reduce re-renders
    if (isStreaming) {
      debounceTimerRef.current = setTimeout(() => {
        setMessagesState([...messagesBufferRef.current]);
        debounceTimerRef.current = null;
      }, 3);
    } else {
      // When streaming ends, update immediately to show final state
      if (wasStreaming) {
        // Flush any pending updates immediately
        setMessagesState([...rawMessages]);
      } else {
        // Not streaming and wasn't streaming - normal update (e.g., hydration)
        setMessagesState([...rawMessages]);
      }
    }

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [rawMessages, status]);

  // Hydrate messages from backend when loading an existing thread
  useEffect(() => {
    if (!sessionId) {
      setIsHydrating(false);
      setMessages([]);
      return;
    }

    const cached = getCachedMessages(sessionId);
    if (cached) {
      setMessages(cached);
      setIsHydrating(false);
      return;
    }

    let cancelled = false;
    setIsHydrating(true);

    fetchThreadMessages(sessionId)
      .then((data) => {
        if (cancelled) return;

        const hydrated = toUIMessages(data);
        setCachedMessages(sessionId, hydrated);
        setMessages(hydrated);

        if (hydrated.length === 0) {
          window.dispatchEvent(new CustomEvent("agents:threads:updated"));
        }
      })
      .catch((err) => {
        console.error("Failed to hydrate thread messages", err);
      })
      .finally(() => {
        if (!cancelled) {
          setIsHydrating(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId, setMessages]);

  const isStreaming = status === "submitted" || status === "streaming";

  const isProgrammaticScrollRef = useRef(false);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    // Mark as programmatic scroll to avoid triggering handleScroll
    isProgrammaticScrollRef.current = true;

    // Small delay to ensure DOM is updated
    setTimeout(() => {
      if (scrollAreaRef.current) {
        const viewport = scrollAreaRef.current.querySelector('[data-slot="scroll-area-viewport"]') as HTMLElement;
        if (viewport) {
          viewport.scrollTo({ top: viewport.scrollHeight, behavior });

          // Reset flag after scroll completes
          setTimeout(
            () => {
              isProgrammaticScrollRef.current = false;
            },
            behavior === "smooth" ? 500 : 100
          );
        }
      }
    }, 50);
  }, []);

  const lastScrollTopRef = useRef(0);

  const handleScroll = useCallback(() => {
    // Ignore programmatic scrolls
    if (isProgrammaticScrollRef.current) return;

    if (!scrollAreaRef.current) return;

    const viewport = scrollAreaRef.current.querySelector('[data-slot="scroll-area-viewport"]') as HTMLElement;
    if (!viewport) return;

    const { scrollTop, scrollHeight, clientHeight } = viewport;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50; // 50px threshold

    // Detect if user is scrolling up manually
    const isScrollingUp = scrollTop < lastScrollTopRef.current;
    lastScrollTopRef.current = scrollTop;

    // If user scrolled up manually (not at bottom), disable auto-scroll immediately
    if ((isScrollingUp || !isAtBottom) && autoScrollEnabled) {
      setAutoScrollEnabled(false);
      isUserScrollingRef.current = true;
    }
    // Don't re-enable automatically - only via button click
  }, [autoScrollEnabled]);

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      const hasText = Boolean(message.text);
      const hasAttachments = Boolean(message.files?.length);

      if (!(hasText || hasAttachments)) {
        return;
      }

      if (singleShot) {
        setMessages([]);
      }

      sendMessage({
        text: message.text ?? "",
        files: message.files
      });

      // Re-enable auto-scroll and scroll to bottom after sending
      setAutoScrollEnabled(true);
      isUserScrollingRef.current = false;
      scrollToBottom();
    },
    [singleShot, sendMessage, setMessages, scrollToBottom]
  );

  const handleSuggestionClick = useCallback(
    (suggestion: string) => {
      if (isStreaming) return;
      handleSubmit({ text: suggestion, files: [] });
    },
    [isStreaming, handleSubmit]
  );

  const handleModelSelect = useCallback(
    (modelId: string) => {
      setSelectedAgentId(modelId);
      selectedAgentIdRef.current = modelId;
      setModelSelectorOpen(false);

      // Save last selected agent to localStorage
      localStorage.setItem("lastSelectedAgentId", modelId);

      // Update URL to reflect the new agent
      navigate({
        to: "/chat/$agentId",
        params: { agentId: modelId },
        search: sessionId ? { session: sessionId } : undefined,
        replace: true
      });

      // Only clear messages if there's no active session (new chat)
      // If there's a sessionId, keep the conversation history
      if (!sessionId) {
        setMessages([]);
      }
    },
    [sessionId, setMessages, navigate]
  );

  // Measure input height for proper padding
  useEffect(() => {
    const updateHeight = () => {
      if (inputRef.current) {
        setInputHeight(inputRef.current.offsetHeight);
      }
    };

    updateHeight();
    const resizeObserver = new ResizeObserver(updateHeight);
    if (inputRef.current) {
      resizeObserver.observe(inputRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, [messages.length, selectedAgent?.suggestions]);

  // Auto-scroll during streaming (only if enabled and not user scrolling)
  useEffect(() => {
    if (isStreaming && autoScrollEnabled && !isUserScrollingRef.current) {
      scrollToBottom("auto");
    }
  }, [messages, isStreaming, autoScrollEnabled, scrollToBottom]);

  // Attach scroll listener
  useEffect(() => {
    if (!scrollAreaRef.current) return;

    const viewport = scrollAreaRef.current.querySelector('[data-slot="scroll-area-viewport"]') as HTMLElement;
    if (!viewport) return;

    viewport.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      viewport.removeEventListener("scroll", handleScroll);
    };
  }, [handleScroll]);

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden">
      <div className="absolute inset-0 flex flex-col overflow-hidden">
        <ScrollArea ref={scrollAreaRef} className="h-full w-full">
          <div className="mx-auto max-w-5xl min-w-0 w-full" style={{ paddingBottom: `${inputHeight}px` }}>
            <Conversation>
              <ConversationContent className="flex flex-col gap-6 px-4 py-4 text-base [&_.group>*]:text-base">
                {messages.length === 0 ? (
                  sessionId && isHydrating ? (
                    <div className="flex h-full items-center justify-center px-4 text-sm text-muted-foreground">
                      Loading conversation...
                    </div>
                  ) : (
                    <ConversationEmptyState
                      title={singleShot ? "Ask anything" : "Start a conversation"}
                      icon={<MessageSquareIcon className="size-6" />}
                      description={
                        singleShot
                          ? "Each request is independent - no conversation history"
                          : "Your messages are saved and the conversation will persist"
                      }
                    />
                  )
                ) : (
                  messages.map((message, messageIndex) => {
                    const isAssistant = message.role === "assistant";
                    const sortedParts = [...(message.parts ?? [])].sort((a, b) => {
                      const order: Record<string, number> = { reasoning: 0, text: 1 };
                      return (order[a?.type] ?? 2) - (order[b?.type] ?? 2);
                    });

                    // Check if text response has started (reasoning is complete)
                    const hasTextPart = sortedParts.some((p) => p?.type === "text" && Boolean((p as any).text));
                    const isLastMessage = messageIndex === messages.length - 1;
                    // Reasoning is streaming only if it's the last message, status is streaming, AND text hasn't started yet
                    const isReasoningStreaming = isLastMessage && isStreaming && !hasTextPart;

                    return (
                      <Message from={message.role} key={message.id}>
                        <MessageContent>
                          {sortedParts.map((part, i) => {
                            if (!part || typeof part !== "object") return null;
                            const textContent = (part as any).text || "";

                            if (part.type === "reasoning") {
                              const reasoningText = (part as any).reasoning || (part as any).text || "";
                              const shouldShowReasoning = (isAssistant && (isReasoningStreaming || reasoningText)) || reasoningText;
                              if (!shouldShowReasoning) return null;
                              return (
                                <Reasoning key={`${message.id}-reasoning-${i}`} isStreaming={isReasoningStreaming}>
                                  <ReasoningTrigger />
                                  <ReasoningContent>{reasoningText}</ReasoningContent>
                                </Reasoning>
                              );
                            }

                            if (part.type === "text") {
                              return <MessageResponse key={`${message.id}-text-${i}`}>{textContent}</MessageResponse>;
                            }
                            return null;
                          })}
                          {isAssistant && sortedParts.length === 0 && <MessageResponse>{extractUserText(message)}</MessageResponse>}
                        </MessageContent>

                        {isAssistant && (
                          <MessageToolbar>
                            <MessageActions>
                              <CopyAction content={extractUserText(message)} />
                            </MessageActions>
                          </MessageToolbar>
                        )}
                      </Message>
                    );
                  })
                )}
              </ConversationContent>
            </Conversation>
          </div>
        </ScrollArea>
      </div>

      {/* Scroll to bottom button - fixed position above input */}
      {!autoScrollEnabled && (
        <Button
          style={{ bottom: `${inputHeight + 16}px` }}
          className="absolute left-1/2 -translate-x-1/2 rounded-full z-30"
          onClick={() => {
            isUserScrollingRef.current = false;
            setAutoScrollEnabled(true);
            scrollToBottom();
          }}
          size="icon"
          variant="outline"
        >
          <ArrowDownIcon className="size-4" />
        </Button>
      )}

      <div ref={inputRef} className="absolute inset-x-0 bottom-0 z-10 shrink-0 bg-background">
        <div className="mx-auto grid max-w-5xl gap-3 px-4 pt-3 pb-4">
          {/* Suggestions */}
          {messages.length === 0 && !singleShot && selectedAgent?.suggestions && selectedAgent.suggestions.length > 0 && (
            <Suggestions className="px-0">
              {selectedAgent.suggestions.map((suggestion, idx) => (
                <Suggestion key={idx} onClick={() => handleSuggestionClick(suggestion)} suggestion={suggestion} />
              ))}
            </Suggestions>
          )}

          {/* Prompt Input */}
          <div className="w-full pb-2">
            <PromptInputProvider>
              <PromptInput className="rounded-xl shadow-sm p-2" globalDrop multiple onSubmit={handleSubmit}>
                <PromptInputAttachmentsDisplay />
                <PromptInputBody>
                  <PromptInputTextarea
                    className="p-4 pb-5 text-[15px]! md:text-[17px]! leading-relaxed resize-none bg-transparent [scrollbar-width:thin] [scrollbar-color:hsl(var(--muted-foreground)/0.2)_transparent] [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:bg-muted-foreground/20 [&::-webkit-scrollbar-thumb]:rounded-full"
                    placeholder="Pergunte algo..."
                  />
                </PromptInputBody>
                <PromptInputFooter>
                  <PromptInputTools className="gap-2">
                    <PromptInputActionMenu>
                      <PromptInputActionMenuTrigger className="size-9 [&_svg]:size-4" />
                      <PromptInputActionMenuContent side="top">
                        <PromptInputActionAddAttachments />
                      </PromptInputActionMenuContent>
                    </PromptInputActionMenu>
                    <PromptInputButton className="h-9 rounded-md px-2 text-sm! font-medium gap-1.5 [&_svg]:size-4.5">
                      <GlobeIcon className="size-4.5" />
                      <span>Search</span>
                    </PromptInputButton>
                    {!singleShot && chatAgents.length > 0 && (
                      <ModelSelector open={modelSelectorOpen} onOpenChange={setModelSelectorOpen}>
                        <ModelSelectorTrigger asChild>
                          <PromptInputButton
                            variant="ghost"
                            className="h-9 rounded-md px-2 text-sm! font-medium gap-1.5 [&_svg]:size-4.5"
                          >
                            {selectedAgent?.chefSlug && (
                              <ModelSelectorLogo provider={selectedAgent.chefSlug} className="size-4.5" />
                            )}
                            {selectedAgent?.name && (
                              <ModelSelectorName className="flex-none">{selectedAgent.name}</ModelSelectorName>
                            )}
                          </PromptInputButton>
                        </ModelSelectorTrigger>
                        <ModelSelectorContent>
                          <ModelSelectorInput placeholder="Search agents..." />
                          <ModelSelectorList>
                            <ModelSelectorEmpty>No agents found.</ModelSelectorEmpty>
                            {Object.entries(agentsByChef).map(([chef, chefAgents]) => (
                              <ModelSelectorGroup heading={chef} key={chef}>
                                {chefAgents.map((agent) => (
                                  <ModelItem
                                    key={agent.id}
                                    agent={agent}
                                    onSelect={handleModelSelect}
                                    selectedAgentId={selectedAgentId}
                                  />
                                ))}
                              </ModelSelectorGroup>
                            ))}
                          </ModelSelectorList>
                        </ModelSelectorContent>
                      </ModelSelector>
                    )}
                  </PromptInputTools>
                  <PromptInputSubmit
                    className="size-9 rounded-lg [&_svg]:size-5"
                    status={isStreaming ? "streaming" : "ready"}
                    onStop={stop}
                  />
                </PromptInputFooter>
              </PromptInput>
            </PromptInputProvider>
          </div>
        </div>
      </div>
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
