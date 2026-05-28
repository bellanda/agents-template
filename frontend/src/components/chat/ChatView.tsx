import { PromptInputProvider } from "@/components/ai-elements/prompt-input";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatConversation } from "@/components/chat/ChatConversation";
import { ChatRejectionDialog } from "@/components/chat/ChatRejectionDialog";
import type { ChatRejection, ChatRejectionEntry } from "@/components/chat/rejection-types";
import { useAgentSelection } from "@/components/chat/use-agent-selection";
import { useChatSession } from "@/components/chat/use-chat-session";
import { useUserId } from "@/hooks/useUserId";
import type { UploadError } from "@/lib/api";
import { useCallback, useState } from "react";

interface ChatViewProps {
  agentId: string;
  sessionId?: string;
  singleShot?: boolean;
}

export function ChatView({ agentId, sessionId, singleShot = false }: ChatViewProps) {
  const [userId] = useUserId();
  const [modelSelectorOpen, setModelSelectorOpen] = useState(false);
  const [rejection, setRejection] = useState<ChatRejection | null>(null);

  const handleModelChanged = useCallback(() => {
    setModelSelectorOpen(false);
  }, []);

  const {
    selectedAgent,
    selectedAgentId,
    selectedAgentIdRef,
    displayAgents,
    agentsByChef,
    handleModelSelect,
  } = useAgentSelection({ agentId, sessionId, onModelChange: handleModelChanged });

  const handleUploadError = useCallback(
    (error: UploadError) => {
      const KNOWN_REASONS: ReadonlySet<ChatRejectionEntry["reason"]> = new Set([
        "image_not_supported",
        "audio_not_supported",
        "video_not_supported",
        "too_large",
        "thread_files_full",
        "thread_images_full",
        "thread_documents_full",
        "user_files_full",
        "user_storage_full",
        "network",
      ]);
      const reason: ChatRejectionEntry["reason"] = KNOWN_REASONS.has(
        error.code as ChatRejectionEntry["reason"]
      )
        ? (error.code as ChatRejectionEntry["reason"])
        : "unsupported_type";
      setRejection({
        modelName: selectedAgent?.name,
        entries: [
          {
            filename: error.filename,
            mediaType: error.mediaType,
            reason,
          },
        ],
      });
    },
    [selectedAgent?.name]
  );

  const session = useChatSession({
    userId,
    sessionId,
    agentName: selectedAgent?.name,
    agentIdRef: selectedAgentIdRef,
    singleShot,
    onUploadError: handleUploadError,
  });

  const onModelSelect = useCallback(
    (id: string) => {
      handleModelSelect(id);
      if (!sessionId) session.clearMessages();
    },
    [handleModelSelect, sessionId, session]
  );

  const handleLocalReject = useCallback(
    (entries: ChatRejectionEntry[]) => {
      setRejection({ modelName: selectedAgent?.name, entries });
    },
    [selectedAgent?.name]
  );

  const handleRejectionClose = useCallback(() => setRejection(null), []);
  const handleSwitchModel = useCallback(() => setModelSelectorOpen(true), []);

  const showModelPicker = !singleShot && displayAgents.length > 0;

  return (
    <PromptInputProvider>
      <div className="bg-background flex h-full min-h-0 w-full flex-col overflow-hidden">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <ChatConversation
            messages={session.messages}
            isStreaming={session.isStreaming}
            isHydrating={session.isHydrating}
            sessionId={sessionId}
            agentName={selectedAgent?.name}
            suggestions={selectedAgent?.suggestions ?? []}
          />
          <ChatComposer
            status={session.status}
            onStop={session.stop}
            onSubmit={session.handleSubmit}
            chatError={session.chatError}
            onClearError={session.clearError}
            selectedAgent={selectedAgent}
            selectedAgentId={selectedAgentId}
            agentsByChef={agentsByChef}
            onModelSelect={onModelSelect}
            modelSelectorOpen={modelSelectorOpen}
            onModelSelectorOpenChange={setModelSelectorOpen}
            showModelPicker={showModelPicker}
            isUploading={session.isUploading}
            onLocalReject={handleLocalReject}
          />
        </div>
      </div>
      <ChatRejectionDialog
        rejection={rejection}
        onClose={handleRejectionClose}
        onSwitchModel={handleSwitchModel}
      />
    </PromptInputProvider>
  );
}
