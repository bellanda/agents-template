import {
  activateAgentConfigVersion,
  fetchAgentConfig,
  fetchAgentConfigVersions,
  saveAgentConfig,
  type AgentConfig,
} from "@/lib/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const agentConfigKey = (agentId: string, userId: string | undefined) =>
  ["agent-config", agentId, userId] as const;
const versionsKey = (agentId: string, userId: string | undefined) =>
  ["agent-config", agentId, userId, "versions"] as const;

export function useAgentConfigQuery(agentId: string | undefined, userId: string | undefined) {
  return useQuery({
    queryKey: agentConfigKey(agentId ?? "", userId),
    queryFn: () => fetchAgentConfig(agentId!, userId),
    enabled: Boolean(agentId && userId),
  });
}

export function useAgentConfigVersionsQuery(
  agentId: string | undefined,
  userId: string | undefined
) {
  return useQuery({
    queryKey: versionsKey(agentId ?? "", userId),
    queryFn: () => fetchAgentConfigVersions(agentId!, userId),
    enabled: Boolean(agentId && userId),
  });
}

/**
 * Save and restore share the same cache discipline: write the response into the config query
 * BEFORE invalidating, otherwise the refetch briefly renders the previous version.
 */
function useConfigMutation<TVars>(
  agentId: string,
  userId: string | undefined,
  mutationFn: (vars: TVars) => Promise<AgentConfig>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (config) => {
      queryClient.setQueryData(agentConfigKey(agentId, userId), config);
      void queryClient.invalidateQueries({ queryKey: versionsKey(agentId, userId) });
    },
  });
}

export const useSaveAgentConfigMutation = (agentId: string, userId: string | undefined) =>
  useConfigMutation(agentId, userId, (markdown: string) =>
    saveAgentConfig(agentId, { system_prompt_markdown: markdown }, userId)
  );

export const useActivateVersionMutation = (agentId: string, userId: string | undefined) =>
  useConfigMutation(agentId, userId, (version: number) =>
    activateAgentConfigVersion(agentId, version, userId)
  );
