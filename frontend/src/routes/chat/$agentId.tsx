import { ChatView } from "@/components/ChatView";
import { createFileRoute } from "@tanstack/react-router";

interface ChatSearch {
  session?: string;
}

export const Route = createFileRoute("/chat/$agentId")({
  validateSearch: (search: Record<string, unknown>): ChatSearch => ({
    session: (search.session as string) ?? undefined
  }),
  component: ChatPage
});

function ChatPage() {
  const { agentId } = Route.useParams();
  const { session } = Route.useSearch();

  // Generate a stable session ID if none provided
  const sessionId = session ?? `${agentId}_${crypto.randomUUID().slice(0, 8)}`;

  return <ChatView key={sessionId} agentId={agentId} sessionId={sessionId} singleShot={false} />;
}
