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
      {/*
        This template's SidebarLayout is a bare flex column (the chat is full-bleed), so the scroll
        area, the 1440 cap and the fluid gutter live here. A product app whose SidebarLayout
        already owns them (gate frontend, layouts.tsx) renders <AgentConfigScreen /> directly:
        the screen itself never sets a width.
        To customize the ChatGPT builder prompt, pass `builderContext` (ChatGptBuilderContext in
        components/agent-config/chatgpt-builder-prompt.ts) as a module-level constant.
      */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[1440px] px-[clamp(1rem,2vw,2rem)] py-4 md:py-6">
          <AgentConfigScreen
            agentId={agent}
            onAgentChange={(agentId) => navigate({ search: { agent: agentId }, replace: true })}
          />
        </div>
      </div>
    </SidebarLayout>
  );
}
