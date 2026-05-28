import { fetchAgents, type AgentModel } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const AGENTS_STALE_TIME_MS = 5 * 60_000;
const LAST_AGENT_STORAGE_KEY = "lastSelectedAgentId";

export const enrichAgent = (agent: AgentModel): AgentModel => {
  const id = agent.id.toLowerCase();
  const desc = agent.description?.toLowerCase() || "";

  let chef = "Custom";
  let chefSlug = "zai";
  const providers: string[] = [];

  if (id.includes("gpt") || desc.includes("openai")) {
    chef = "OpenAI";
    chefSlug = "openai";
  } else if (id.includes("claude") || desc.includes("anthropic")) {
    chef = "Anthropic";
    chefSlug = "anthropic";
  } else if (id.includes("gemini") || desc.includes("google")) {
    chef = "Google";
    chefSlug = "google";
  } else if (id.includes("deepseek") || desc.includes("deepseek")) {
    chef = "DeepSeek";
    chefSlug = "deepseek";
  } else if (id.includes("qwen") || desc.includes("qwen")) {
    chef = "Alibaba";
    chefSlug = "alibaba";
  } else if (id.includes("kimi") || desc.includes("moonshot")) {
    chef = "Moonshot";
    chefSlug = "moonshotai";
  } else if (id.includes("minimax") || desc.includes("minimax")) {
    chef = "MiniMax";
    chefSlug = "zai";
  }

  if (desc.includes("chutes")) providers.push("chutes");
  if (desc.includes("groq")) providers.push("groq");
  if (desc.includes("google")) providers.push("google");
  if (desc.includes("nvidia")) providers.push("nvidia");
  if (desc.includes("cerebras")) providers.push("cerebras");

  return { ...agent, chef, chefSlug, providers };
};

interface UseAgentSelectionOptions {
  agentId: string;
  sessionId: string | undefined;
  onModelChange?: () => void;
}

export function useAgentSelection({ agentId, sessionId, onModelChange }: UseAgentSelectionOptions) {
  const navigate = useNavigate();
  const [selectedAgentId, setSelectedAgentId] = useState(agentId);
  const selectedAgentIdRef = useRef(agentId);

  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
    staleTime: AGENTS_STALE_TIME_MS,
  });

  const resolveValidAgentId = useCallback((current: string, list: AgentModel[]): string => {
    if (list.length === 0) return current;
    const isValid = list.some((a) => a.id === current);
    if (isValid) return current;
    const lastSaved = localStorage.getItem(LAST_AGENT_STORAGE_KEY);
    const lastValid = lastSaved && list.some((a) => a.id === lastSaved);
    return lastValid ? lastSaved : list[0]!.id;
  }, []);

  useEffect(() => {
    if (agents.length === 0) return;
    const validId = resolveValidAgentId(agentId, agents);
    setSelectedAgentId(validId);
    selectedAgentIdRef.current = validId;
    localStorage.setItem(LAST_AGENT_STORAGE_KEY, validId);
    if (validId !== agentId) {
      navigate({
        to: "/chat/$agentId",
        params: { agentId: validId },
        search: sessionId ? { session: sessionId } : undefined,
        replace: true,
      });
    }
  }, [agentId, agents, sessionId, navigate, resolveValidAgentId]);

  const selectedAgent = useMemo(() => {
    const agent = agents.find((a) => a.id === selectedAgentId);
    return agent ? enrichAgent(agent) : undefined;
  }, [agents, selectedAgentId]);

  const chatAgents = useMemo(
    () => agents.filter((a) => a.save_to_db !== false).map(enrichAgent),
    [agents]
  );

  const displayAgents = chatAgents.length > 0 ? chatAgents : agents.map(enrichAgent);

  const agentsByChef = useMemo(() => {
    const groups: Record<string, AgentModel[]> = {};
    displayAgents.forEach((agent) => {
      const chef = agent.chef || "Custom";
      if (!groups[chef]) groups[chef] = [];
      groups[chef]!.push(agent);
    });
    return groups;
  }, [displayAgents]);

  const handleModelSelect = useCallback(
    (modelId: string) => {
      setSelectedAgentId(modelId);
      selectedAgentIdRef.current = modelId;
      localStorage.setItem(LAST_AGENT_STORAGE_KEY, modelId);

      navigate({
        to: "/chat/$agentId",
        params: { agentId: modelId },
        search: sessionId ? { session: sessionId } : undefined,
        replace: true,
      });

      onModelChange?.();
    },
    [sessionId, navigate, onModelChange]
  );

  return {
    agents,
    selectedAgent,
    selectedAgentId,
    selectedAgentIdRef,
    displayAgents,
    agentsByChef,
    handleModelSelect,
  };
}
