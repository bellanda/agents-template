import { ChatView } from "@/components/chat";
import { SidebarLayout } from "@/components/layouts";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/agent/$agentId")({
  component: AgentPage
});

function AgentPage() {
  const { agentId } = Route.useParams();

  return (
    <SidebarLayout>
      <ChatView agentId={agentId} singleShot={true} />
    </SidebarLayout>
  );
}
