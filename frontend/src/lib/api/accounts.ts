import type { AppStyleId } from "@/lib/appearance/app-styles";

const ACCOUNTS_BASE = "/api/v1/accounts";

export interface AccountMe {
  id: string;
  uiPreferences: { appStyle?: unknown };
}

// Identidade aberta do template (`services/auth.py`): o backend lê `X-User-Id`.
function identityHeaders(userId: string): Record<string, string> {
  return { "X-User-Id": userId };
}

export async function fetchAccountMe(userId: string): Promise<AccountMe> {
  const res = await fetch(`${ACCOUNTS_BASE}/me`, { headers: identityHeaders(userId) });
  if (!res.ok) throw new Error(`GET /accounts/me failed: HTTP ${res.status}`);
  const body = (await res.json()) as { id: string; ui_preferences?: { app_style?: unknown } };
  return { id: body.id, uiPreferences: { appStyle: body.ui_preferences?.app_style } };
}

export async function patchAppStyle(userId: string, appStyle: AppStyleId): Promise<void> {
  const res = await fetch(`${ACCOUNTS_BASE}/me/ui-preferences`, {
    method: "PATCH",
    headers: { ...identityHeaders(userId), "Content-Type": "application/json" },
    body: JSON.stringify({ app_style: appStyle }),
  });
  if (!res.ok) throw new Error(`PATCH /accounts/me/ui-preferences failed: HTTP ${res.status}`);
}
