import { ChatView } from "@/components/ChatView";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/agent/$agentId")({
  component: AgentPage
});

function AgentPage() {
  const { agentId } = Route.useParams();

  return <ChatView agentId={agentId} singleShot={true} />;
}
