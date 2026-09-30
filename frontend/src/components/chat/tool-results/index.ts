import type { ComponentType } from "react";
import { ActionConfirmationResult } from "./action-confirmation-result";
import type { ToolResultEnvelope } from "./types";

/**
 * Registry `envelope.type -> renderer`. Only generic renderers live here; a product app adds its
 * own entries (e.g. `my_domain_card`) instead of branching in ChatMessage. Types without an entry
 * fall back to the collapsed tool block with the raw JSON output.
 */
const REGISTRY: Record<string, ComponentType<{ data: never }>> = {
  action_confirmation: ActionConfirmationResult as unknown as ComponentType<{ data: never }>,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Parses a tool output (object or JSON string) into an envelope, or null if it is not one. */
export function parseToolEnvelope(output: unknown): ToolResultEnvelope | null {
  let value = output;
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch {
      return null;
    }
  }
  if (!isRecord(value) || typeof value.type !== "string" || !isRecord(value.data)) return null;
  return { type: value.type, data: value.data };
}

/** Renderer for this output's envelope, with its data; null when there is no registered card. */
export function resolveToolResult(
  output: unknown
): { Renderer: ComponentType<{ data: never }>; data: Record<string, unknown> } | null {
  const envelope = parseToolEnvelope(output);
  const Renderer = envelope ? REGISTRY[envelope.type] : undefined;
  return envelope && Renderer ? { Renderer, data: envelope.data } : null;
}
