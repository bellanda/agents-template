/**
 * TanStack Query bindings of the config screen to the template backend
 * (`routes/agents/agent_config.py`: GET/PUT `/agents/{id}/config`, GET `.../config/versions`,
 * POST `.../config/versions/{v}/activate`). This is one of the two API-bound files of the folder
 * (with AgentConfigScreen): an app with another wire format (org-scoped URLs, camelCase client)
 * rewrites just these, and keeps InstructionsCard / VersionsPanel / MarkdownPreview verbatim.
 */
import type { AgentVersionItem } from "@/components/agent-config/agent-version";
import {
  activateAgentConfigVersion,
  fetchAgentConfig,
  fetchAgentConfigVersions,
  saveAgentConfig,
  type AgentConfig,
  type AgentConfigVersion,
} from "@/lib/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const agentConfigKey = (agentId: string, userId: string | undefined) =>
  ["agent-config", agentId, userId] as const;
const versionsKey = (agentId: string, userId: string | undefined) =>
  ["agent-config", agentId, userId, "versions"] as const;

/** Wire (snake_case) -> view-model the presentational components take. */
const toVersionItem = (row: AgentConfigVersion): AgentVersionItem => ({
  version: row.version,
  note: row.note,
  createdAt: row.created_at,
  markdown: row.system_prompt_markdown,
});
const toVersionItems = (rows: AgentConfigVersion[]): AgentVersionItem[] => rows.map(toVersionItem);

export function useAgentConfigQuery(agentId: string | undefined, userId: string | undefined) {
  return useQuery({
    queryKey: agentConfigKey(agentId ?? "", userId),
    queryFn: () => fetchAgentConfig(agentId!, userId),
    enabled: Boolean(agentId && userId),
  });
}

/** Newest first (the backend orders and bounds the list). */
export function useAgentConfigVersionsQuery(
  agentId: string | undefined,
  userId: string | undefined
) {
  return useQuery({
    queryKey: versionsKey(agentId ?? "", userId),
    queryFn: () => fetchAgentConfigVersions(agentId!, userId),
    select: toVersionItems,
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

export interface SaveAgentConfigVariables {
  markdown: string;
  /** Optional publish note shown in the version history. */
  note?: string;
}

export const useSaveAgentConfigMutation = (agentId: string, userId: string | undefined) =>
  useConfigMutation(agentId, userId, ({ markdown, note }: SaveAgentConfigVariables) =>
    saveAgentConfig(agentId, { system_prompt_markdown: markdown, note }, userId)
  );

export const useActivateVersionMutation = (agentId: string, userId: string | undefined) =>
  useConfigMutation(agentId, userId, (version: number) =>
    activateAgentConfigVersion(agentId, version, userId)
  );
