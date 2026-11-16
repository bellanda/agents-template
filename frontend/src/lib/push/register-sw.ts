/**
 * Registro do service worker no boot (`initInstallPrompt()` em `lib/pwa/install-prompt.ts`).
 *
 * "Fire and forget": Chromium mais antigo só considera o app instalável com SW ativo, e o
 * `public/sw.js` não tem handler de `fetch` (sem cache offline, sem custo). Nunca lança.
 * App com push acrescenta aqui `registerPushServiceWorker`/`getExistingSubscription` (ver o
 * `lib/push/register-sw.ts` do kailos).
 */
const SW_URL = "/sw.js";

export async function registerServiceWorkerAtBoot(): Promise<void> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  try {
    await navigator.serviceWorker.register(SW_URL, { scope: "/" });
  } catch {
    // Sem SW o app só perde a instalabilidade; nunca pode quebrar o boot.
  }
}
