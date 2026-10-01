import type { ChatGptBuilderContext } from "@/components/agent-config/chatgpt-builder-prompt";
import { InstructionsCard } from "@/components/agent-config/InstructionsCard";
import {
  useActivateVersionMutation,
  useAgentConfigQuery,
  useAgentConfigVersionsQuery,
  useSaveAgentConfigMutation,
} from "@/components/agent-config/use-agent-config";
import { VersionsPanel } from "@/components/agent-config/VersionsPanel";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useUserId } from "@/hooks/useUserId";
import { fetchAgents, MAX_PROMPT_MARKDOWN_CHARS, type AgentConfig } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { toast } from "sonner";

/** What an app extra needs to know about the agent being configured. */
export interface AgentConfigSlotContext {
  agentId: string;
  config: AgentConfig;
}

interface AgentConfigScreenProps {
  /** Selected agent id (registry key from GET /agents); defaults to the first agent. */
  agentId: string | undefined;
  onAgentChange: (agentId: string) => void;
  /** Domain text for the "Montar com o ChatGPT" prompt. Keep the object reference stable. */
  builderContext?: ChatGptBuilderContext;
  /** False = view-only (user lacks the manage permission): no edit, no restore. Default true. */
  canEdit?: boolean;
  /** App extra ABOVE the instructions (e.g. the "Atendente de IA" on/off ToggleCard). */
  renderBeforeInstructions?: (context: AgentConfigSlotContext) => ReactNode;
  /** App extras BETWEEN instructions and history (e.g. capture toggles, AgentTester, documents). */
  renderAfterInstructions?: (context: AgentConfigSlotContext) => ReactNode;
}

/**
 * Tenant agent config screen: pick an agent, edit its Markdown, browse/restore versions.
 *
 * Canonical composition (decision 2026-10-01, frontend standardization): [before slot] ->
 * InstructionsCard -> [after slot] -> VersionsPanel. App-specific blocks (toggles, tester,
 * documents) are injected through the two render slots, so this folder never imports from an
 * app. The screen owns NO width/scroll: the layout (gate frontend) does — see routes/agent-config.
 *
 * API-bound file: with `use-agent-config.ts` it is what an app adapts to its own routes/permission
 * hook; InstructionsCard, VersionsPanel, MarkdownPreview and chatgpt-builder-prompt are copied as is.
 */
export function AgentConfigScreen({
  agentId,
  onAgentChange,
  builderContext,
  canEdit = true,
  renderBeforeInstructions,
  renderAfterInstructions,
}: AgentConfigScreenProps) {
  const [userId] = useUserId();
  // Same query key as the chat's agent selection, so the list is shared from cache.
  const { data: agents = [], isLoading: agentsLoading } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
    staleTime: 5 * 60_000,
  });
  const selectedId = agentId ?? agents[0]?.id;

  const config = useAgentConfigQuery(selectedId, userId);
  const versions = useAgentConfigVersionsQuery(selectedId, userId);
  const save = useSaveAgentConfigMutation(selectedId ?? "", userId);
  const activate = useActivateVersionMutation(selectedId ?? "", userId);

  const handleSave = (markdown: string, note: string | undefined) =>
    save.mutate(
      { markdown, note },
      {
        onSuccess: () => toast.success("Nova versão salva."),
        onError: (err) => toast.error(err.message),
      }
    );
  const handleActivate = (version: number) =>
    activate.mutate(version, {
      onSuccess: () => toast.success(`Versão ${version} restaurada como nova versão.`),
      onError: (err) => toast.error(err.message),
    });

  const slotContext: AgentConfigSlotContext | null =
    selectedId && config.data ? { agentId: selectedId, config: config.data } : null;

  return (
    <div className="space-y-6">
      {/* One agent = nothing to choose; the selector only earns its row with 2+ agents. */}
      {agents.length > 1 && (
        <div className="max-w-sm space-y-1.5">
          <Label htmlFor="agent-config-agent">Agente</Label>
          <Select value={selectedId ?? ""} onValueChange={onAgentChange} disabled={agentsLoading}>
            <SelectTrigger id="agent-config-agent" className="w-full max-md:h-11">
              <SelectValue placeholder="Selecione um agente" />
            </SelectTrigger>
            <SelectContent>
              {agents.map((agent) => (
                <SelectItem key={agent.id} value={agent.id}>
                  {agent.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {config.isLoading && <Skeleton className="h-64 w-full" />}
      {config.isError && (
        <p className="text-destructive text-sm">
          Não foi possível carregar as instruções: {config.error.message}
        </p>
      )}
      {config.data && slotContext && (
        <>
          {renderBeforeInstructions?.(slotContext)}
          <InstructionsCard
            key={`${config.data.agent_id}:${config.data.active_version}`}
            markdown={config.data.system_prompt_markdown}
            maxChars={MAX_PROMPT_MARKDOWN_CHARS}
            builderContext={builderContext}
            readOnly={!canEdit}
            saving={save.isPending}
            onSave={handleSave}
          />
          {renderAfterInstructions?.(slotContext)}
          <VersionsPanel
            versions={versions.data ?? []}
            activeVersion={config.data.active_version}
            isLoading={versions.isLoading}
            canActivate={canEdit}
            activatingVersion={activate.isPending ? activate.variables : null}
            onActivate={handleActivate}
          />
        </>
      )}
    </div>
  );
}
