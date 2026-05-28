import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { ChatEmptyHero } from "@/components/chat/ChatEmptyHero";
import { ChatMessage } from "@/components/chat/ChatMessage";
import type { AgentSuggestion } from "@/lib/api";
import type { UIMessage } from "ai";

interface ChatConversationProps {
  messages: UIMessage[];
  isStreaming: boolean;
  isHydrating: boolean;
  sessionId: string | undefined;
  agentName: string | undefined;
  suggestions: AgentSuggestion[];
}

export function ChatConversation({
  messages,
  isStreaming,
  isHydrating,
  sessionId,
  agentName,
  suggestions,
}: ChatConversationProps) {
  const isEmpty = messages.length === 0;
  const showHydrating = isEmpty && Boolean(sessionId) && isHydrating;
  const showHero = isEmpty && !showHydrating;

  return (
    <Conversation className="min-h-0 flex-1">
      <ConversationContent className="px-0 py-0">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-10 px-3 py-6 text-base sm:px-4 lg:max-w-5xl xl:max-w-6xl">
          {showHydrating && (
            <div className="text-muted-foreground flex h-full items-center justify-center px-4 text-sm">
              Loading conversation...
            </div>
          )}
          {showHero && <ChatEmptyHero agentName={agentName} suggestions={suggestions} />}
          {!isEmpty &&
            messages.map((message, index) => (
              <ChatMessage
                key={message.id}
                message={message}
                isLastMessage={index === messages.length - 1}
                isStreaming={isStreaming}
              />
            ))}
        </div>
      </ConversationContent>
      <ConversationScrollButton />
    </Conversation>
  );
}
