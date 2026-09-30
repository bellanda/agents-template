import { AgentConfigScreen } from "@/components/agent-config";
import { SidebarLayout } from "@/components/layouts";
import { createFileRoute, useNavigate } from "@tanstack/react-router";

interface AgentConfigSearch {
  agent?: string;
}

export const Route = createFileRoute("/agent-config")({
  validateSearch: (search: Record<string, unknown>): AgentConfigSearch => ({
    agent: typeof search.agent === "string" ? search.agent : undefined,
  }),
  component: AgentConfigPage,
});

function AgentConfigPage() {
  const { agent } = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });

  return (
    <SidebarLayout>
      <AgentConfigScreen
        agentId={agent}
        onAgentChange={(agentId) => navigate({ search: { agent: agentId }, replace: true })}
      />
    </SidebarLayout>
  );
}
