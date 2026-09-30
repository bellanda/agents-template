import { InstructionsCard } from "@/components/agent-config/InstructionsCard";
import { VersionsPanel } from "@/components/agent-config/VersionsPanel";
import {
  useActivateVersionMutation,
  useAgentConfigQuery,
  useAgentConfigVersionsQuery,
  useSaveAgentConfigMutation,
} from "@/components/agent-config/use-agent-config";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useUserId } from "@/hooks/useUserId";
import { fetchAgents } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

interface AgentConfigScreenProps {
  /** Selected agent id (registry key from GET /agents); defaults to the first agent. */
  agentId: string | undefined;
  onAgentChange: (agentId: string) => void;
}

/** Tenant agent instructions: pick an agent, edit its Markdown, browse/restore versions. */
export function AgentConfigScreen({ agentId, onAgentChange }: AgentConfigScreenProps) {
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

  const handleSave = (markdown: string) =>
    save.mutate(markdown, {
      onSuccess: () => toast.success("Nova versão salva."),
      onError: (err) => toast.error(err.message),
    });
  const handleActivate = (version: number) =>
    activate.mutate(version, {
      onSuccess: () => toast.success(`Versão ${version} restaurada como nova versão.`),
      onError: (err) => toast.error(err.message),
    });

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-[1440px] space-y-6 px-[clamp(1rem,2vw,2rem)] py-4 md:py-6">
        <div className="max-w-sm space-y-1.5">
          <Label htmlFor="agent-config-agent">Agente</Label>
          <Select value={selectedId ?? ""} onValueChange={onAgentChange} disabled={agentsLoading}>
            <SelectTrigger id="agent-config-agent" className="w-full">
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

        {config.isLoading && <Skeleton className="h-64 w-full" />}
        {config.isError && (
          <p className="text-destructive text-sm">
            Não foi possível carregar as instruções: {config.error.message}
          </p>
        )}
        {config.data && (
          <>
            <InstructionsCard
              key={`${config.data.agent_id}:${config.data.active_version}`}
              markdown={config.data.system_prompt_markdown}
              saving={save.isPending}
              onSave={handleSave}
            />
            <VersionsPanel
              versions={versions.data ?? []}
              activeVersion={config.data.active_version}
              isLoading={versions.isLoading}
              activatingVersion={activate.isPending ? activate.variables : null}
              onActivate={handleActivate}
            />
          </>
        )}
      </div>
    </div>
  );
}
