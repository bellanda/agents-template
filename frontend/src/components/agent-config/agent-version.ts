/**
 * View-model of one saved version, shared by VersionsPanel and VersionPreviewDialog.
 *
 * Deliberately NOT the API type: the presentational components in this folder never import from
 * `@/lib/api`, so apps with a different wire format (camelCase `ApiClient`, org-scoped routes)
 * copy them verbatim and map their rows in the hook (`use-agent-config.ts` does it with `select`).
 */
export interface AgentVersionItem {
  version: number;
  /** Publish note typed on save; null when none ("Restaurada da vN" on a restore). */
  note: string | null;
  /** ISO 8601 timestamp. */
  createdAt: string;
  /** Full text of the version, for the preview and the diff against the active one. */
  markdown: string;
}

const dateTimeFormat = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

/** pt-BR short date+time; "—" for an invalid timestamp (gate frontend, DateTime rule). */
export function formatVersionDateTime(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  return Number.isNaN(date.getTime()) ? "—" : dateTimeFormat.format(date);
}
