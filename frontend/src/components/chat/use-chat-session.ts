import type { PromptInputMessage } from "@/components/ai-elements/prompt-input";
import { threadsQueryKey } from "@/components/chat/use-threads-query";
import { fetchThreadMessages, uploadFile, UploadError } from "@/lib/api";
import {
  getCachedMessages,
  invalidateThread,
  setCachedMessages,
  toUIMessages,
} from "@/lib/thread-messages-cache";
import { useChat } from "@ai-sdk/react";
import { useQueryClient } from "@tanstack/react-query";
import type { FileUIPart, UIMessage } from "ai";
import { DefaultChatTransport } from "ai";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

const STREAM_THROTTLE_MS = 32;

async function fileFromUIPart(part: FileUIPart): Promise<File> {
  const response = await fetch(part.url);
  const blob = await response.blob();
  return new File([blob], part.filename || "file", {
    type: part.mediaType || blob.type || "application/octet-stream",
  });
}

async function persistFiles(
  parts: FileUIPart[],
  modelId: string,
  userId: string | undefined,
  sessionId: string | undefined
): Promise<FileUIPart[]> {
  if (parts.length === 0) return parts;
  return Promise.all(
    parts.map(async (part) => {
      if (part.url && !part.url.startsWith("data:") && !part.url.startsWith("blob:")) {
        return part;
      }
      const file = await fileFromUIPart(part);
      const uploaded = await uploadFile(file, modelId, userId, sessionId);
      return {
        ...part,
        url: uploaded.url,
        filename: uploaded.filename,
        mediaType: uploaded.mediaType,
      } satisfies FileUIPart;
    })
  );
}

interface UseChatSessionOptions {
  userId: string | undefined;
  sessionId: string | undefined;
  agentName: string | undefined;
  agentIdRef: React.MutableRefObject<string>;
  singleShot: boolean;
  onUploadError?: (error: UploadError) => void;
}

export function useChatSession({
  userId,
  sessionId,
  agentName,
  agentIdRef,
  singleShot,
  onUploadError,
}: UseChatSessionOptions) {
  const queryClient = useQueryClient();
  const [isHydrating, setIsHydrating] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: "/api/v1/agents/chat/completions",
        // Identity flows via the X-User-Id header (backend get_auth_context),
        // never the request body. Swap for `Authorization: Bearer` with real auth.
        headers: (): Record<string, string> => (userId ? { "X-User-Id": userId } : {}),
        body: () => ({
          model: agentIdRef.current,
          agent_name: agentName || agentIdRef.current,
          stream: true,
          ...(sessionId ? { session_id: sessionId } : {}),
        }),
      }),
    [userId, sessionId, agentName, agentIdRef]
  );

  const {
    messages: rawMessages,
    sendMessage,
    setMessages,
    status,
    stop,
    error: chatError,
    clearError,
  } = useChat({
    id: sessionId,
    transport,
    onFinish() {
      if (sessionId) invalidateThread(sessionId);
      void queryClient.invalidateQueries({ queryKey: threadsQueryKey(userId) });
    },
    onError(err) {
      toast.error(err.message ?? "Erro no assistente");
    },
  });

  const [messages, setMessagesState] = useState<UIMessage[]>(rawMessages);
  const messagesBufferRef = useRef<UIMessage[]>(rawMessages);
  const lastEmitRef = useRef<number>(0);
  const pendingTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const isStreaming = status === "submitted" || status === "streaming";
    messagesBufferRef.current = rawMessages;

    if (!isStreaming) {
      if (pendingTimerRef.current) {
        clearTimeout(pendingTimerRef.current);
        pendingTimerRef.current = null;
      }
      setMessagesState([...rawMessages]);
      lastEmitRef.current = 0;
      return;
    }

    const now = performance.now();
    const elapsed = now - lastEmitRef.current;

    if (elapsed >= STREAM_THROTTLE_MS) {
      lastEmitRef.current = now;
      setMessagesState([...rawMessages]);
      return;
    }

    if (pendingTimerRef.current) return;

    pendingTimerRef.current = setTimeout(() => {
      pendingTimerRef.current = null;
      lastEmitRef.current = performance.now();
      setMessagesState([...messagesBufferRef.current]);
    }, STREAM_THROTTLE_MS - elapsed);

    return () => {
      if (pendingTimerRef.current) {
        clearTimeout(pendingTimerRef.current);
        pendingTimerRef.current = null;
      }
    };
  }, [rawMessages, status]);

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

    fetchThreadMessages(sessionId, userId)
      .then((data) => {
        if (cancelled) return;
        const hydrated = toUIMessages(data);
        setCachedMessages(sessionId, hydrated);
        setMessages(hydrated);
        if (hydrated.length === 0) {
          void queryClient.invalidateQueries({ queryKey: threadsQueryKey(userId) });
        }
      })
      .catch((err) => {
        console.error("Failed to hydrate thread messages", err);
      })
      .finally(() => {
        if (!cancelled) setIsHydrating(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId, setMessages, queryClient, userId]);

  const isStreaming = status === "submitted" || status === "streaming";

  const handleSubmit = useCallback(
    async (message: PromptInputMessage) => {
      // Anexo SEM texto é mensagem válida: system prompt + documento já bastam para a IA
      // começar. Nunca exija texto aqui nem desabilite o botão de enviar por causa dele.
      const hasText = Boolean(message.text);
      const hasAttachments = Boolean(message.files?.length);
      if (!(hasText || hasAttachments)) return;

      let files = message.files ?? [];
      if (files.length > 0) {
        setIsUploading(true);
        try {
          files = await persistFiles(files, agentIdRef.current, userId, sessionId);
        } catch (err) {
          setIsUploading(false);
          if (err instanceof UploadError) {
            if (onUploadError) {
              onUploadError(err);
            } else {
              toast.error(err.message);
            }
          } else {
            toast.error(err instanceof Error ? err.message : "Failed to upload attachment.");
          }
          return;
        }
        setIsUploading(false);
      }

      if (singleShot) setMessages([]);

      sendMessage({
        text: message.text ?? "",
        files,
      });
    },
    [singleShot, sendMessage, setMessages, agentIdRef, onUploadError]
  );

  const clearMessages = useCallback(() => setMessages([]), [setMessages]);

  return {
    messages,
    sendMessage,
    status,
    stop,
    chatError,
    clearError,
    isStreaming,
    isHydrating,
    isUploading,
    handleSubmit,
    clearMessages,
  };
}
