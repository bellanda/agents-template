/**
 * Standard envelope a backend tool may return: `{"type": "<discriminator>", "data": {...}}`.
 * It arrives as the SSE `tool-output-available` output, either as an object or as a JSON string.
 * Keys stay snake_case (as sent); there is no camelCase conversion in this template.
 */
export interface ToolResultEnvelope<TData = Record<string, unknown>> {
  type: string;
  data: TData;
}

/** Data of the generic `action_confirmation` envelope. */
export interface ActionConfirmationData {
  status: "success" | "error";
  message: string;
  [key: string]: unknown;
}
