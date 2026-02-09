import { ChatView } from "@/components/ChatView";
import { SidebarLayout } from "@/components/layouts";
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

  return (
    <SidebarLayout>
      <ChatView agentId={agentId} sessionId={session} singleShot={false} />
    </SidebarLayout>
  );
}
