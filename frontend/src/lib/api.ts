const API_BASE = "/api/v1/agents";

// ── Types ──────────────────────────────────────────────────────────────────────

export interface AgentModel {
  id: string;
  name: string;
  description: string;
  save_to_db: boolean;
  suggestions?: string[];
  provider?: string;
  providers?: string[];
  chef?: string;
  chefSlug?: string;
}

export interface Thread {
  thread_id: string;
  agent_id: string;
  preview: string;
  message_count: number;
  created_at: string;
}

export interface ThreadMessage {
  role: string;
  content: string;
  id?: string;
  reasoning?: string;
}

// ── API Functions ──────────────────────────────────────────────────────────────

export async function fetchAgents(): Promise<AgentModel[]> {
  const res = await fetch(`${API_BASE}`);
  if (!res.ok) throw new Error("Failed to fetch agents");
  const data = await res.json();
  return data.data ?? [];
}

export async function fetchThreads(agentId?: string, userId?: string): Promise<Thread[]> {
  const params = new URLSearchParams();
  if (agentId) params.append("agent_id", agentId);
  if (userId) params.append("user_id", userId);
  const queryString = params.toString();
  const res = await fetch(`${API_BASE}/threads${queryString ? `?${queryString}` : ""}`);
  if (!res.ok) throw new Error("Failed to fetch threads");
  const data = await res.json();
  return data.threads ?? [];
}

export async function fetchThreadMessages(threadId: string): Promise<ThreadMessage[]> {
  const res = await fetch(`${API_BASE}/threads/${threadId}`);
  if (!res.ok) throw new Error("Failed to fetch thread messages");
  const data = await res.json();
  return data.messages ?? [];
}

/** Prefetch and cache thread messages. Call on sidebar thread hover for instant switch on click. */
export async function prefetchThreadMessages(threadId: string): Promise<void> {
  const { getCachedMessages, cacheThreadMessages } = await import("./thread-messages-cache");
  if (getCachedMessages(threadId)) return;
  const data = await fetchThreadMessages(threadId);
  cacheThreadMessages(threadId, data);
}

export async function deleteThread(threadId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/threads/${threadId}`, {
    method: "DELETE"
  });
  if (!res.ok) throw new Error("Failed to delete thread");
}
