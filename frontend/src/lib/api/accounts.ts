import type { AppStyleId } from "@/lib/appearance/app-styles";
import type { FontSizeId } from "@/lib/appearance/font-size";

const ACCOUNTS_BASE = "/api/v1/accounts";

export interface AccountMe {
  id: string;
  uiPreferences: { appStyle?: unknown; fontSize?: unknown };
}

// Identidade aberta do template (`services/auth.py`): o backend lê `X-User-Id`.
function identityHeaders(userId: string): Record<string, string> {
  return { "X-User-Id": userId };
}

export async function fetchAccountMe(userId: string): Promise<AccountMe> {
  const res = await fetch(`${ACCOUNTS_BASE}/me`, { headers: identityHeaders(userId) });
  if (!res.ok) throw new Error(`GET /accounts/me failed: HTTP ${res.status}`);
  const body = (await res.json()) as {
    id: string;
    ui_preferences?: { app_style?: unknown; font_size?: unknown };
  };
  return {
    id: body.id,
    uiPreferences: {
      appStyle: body.ui_preferences?.app_style,
      fontSize: body.ui_preferences?.font_size,
    },
  };
}

export async function patchAppStyle(
  userId: string,
  appStyle: AppStyleId,
  fontSize?: FontSizeId
): Promise<void> {
  const res = await fetch(`${ACCOUNTS_BASE}/me/ui-preferences`, {
    method: "PATCH",
    headers: { ...identityHeaders(userId), "Content-Type": "application/json" },
    body: JSON.stringify({ app_style: appStyle, font_size: fontSize }),
  });
  if (!res.ok) throw new Error(`PATCH /accounts/me/ui-preferences failed: HTTP ${res.status}`);
}
