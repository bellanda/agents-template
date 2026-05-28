import type { UIMessage } from "ai";
import type { ThreadMessage } from "./api";

const CACHE_TTL_MS = 60_000;

const cache = new Map<string, { messages: UIMessage[]; timestamp: number }>();

export function toUIMessages(data: ThreadMessage[]): UIMessage[] {
  return data
    .map((m, index) => {
      const role = m.role === "user" ? "user" : "assistant";
      const text = String(m.content || "");
      const reasoning = m.reasoning ? String(m.reasoning) : undefined;
      const persistedParts = Array.isArray(m.parts) ? m.parts : null;

      if (!text.trim() && !reasoning && !persistedParts?.length) return null;

      const parts: unknown[] = [];

      if (persistedParts && persistedParts.length > 0) {
        for (const part of persistedParts) parts.push(part);
      } else {
        if (reasoning) parts.push({ type: "reasoning", reasoning });
        if (text) parts.push({ type: "text", text });
      }

      return {
        id: m.id || `${role}-${index}`,
        role: role as "user" | "assistant",
        parts: parts as UIMessage["parts"],
      } as UIMessage;
    })
    .filter((msg): msg is UIMessage => msg !== null);
}

export function getCachedMessages(threadId: string): UIMessage[] | null {
  const entry = cache.get(threadId);
  if (!entry || Date.now() - entry.timestamp > CACHE_TTL_MS) {
    if (entry) cache.delete(threadId);
    return null;
  }
  return entry.messages;
}

export function setCachedMessages(threadId: string, messages: UIMessage[]): void {
  cache.set(threadId, { messages, timestamp: Date.now() });
}

export function cacheThreadMessages(threadId: string, data: ThreadMessage[]): void {
  setCachedMessages(threadId, toUIMessages(data));
}

export function invalidateThread(threadId: string): void {
  cache.delete(threadId);
}
