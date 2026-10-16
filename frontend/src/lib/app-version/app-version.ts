/**
 * Lógica pura da atualização forçada pós-deploy (decisão do usuário 2026-10-16).
 *
 * Problema: aba aberta durante um deploy segue com o bundle velho; ao navegar, o chunk com hash
 * antigo some (404) e a tela quebra, e o usuário só se salva com Ctrl+Shift+R. O build emite
 * `/version.json` (no-store no nginx); o watcher compara com o `__APP_BUILD_ID__` embutido e
 * recarrega a página. Este arquivo não toca React nem o DOM global — tudo injetável p/ teste.
 *
 * `location.reload()` aqui é EXCEÇÃO deliberada à regra do pwa-mobile §3 (que proíbe reload só
 * no botão de "recarregar dados"): trocar o bundle exige recarregar o documento. A sessão volta
 * pelo cookie de refresh no boot, igual a um F5.
 */

export const VERSION_URL = "/version.json";
export const CHECK_INTERVAL_MS = 5 * 60 * 1000;
export const COUNTDOWN_SECONDS = 15;
/** Janela em que um 2º erro de chunk NÃO recarrega de novo (anti-loop do preloadError). */
export const PRELOAD_RELOAD_COOLDOWN_MS = 60 * 1000;

const RELOADED_FOR_KEY = "app-version:reloaded-for";
const PRELOAD_RELOAD_AT_KEY = "app-version:preload-reload-at";

export type UpdateAction =
  "wait" | "reload-now" | "reload-on-navigation" | "countdown" | "banner-only";

export interface UpdateState {
  updatePending: boolean;
  /** Aba oculta: ninguém vê, então recarregar é de graça. */
  isHidden: boolean;
  /** Uma navegação do router está começando agora. */
  isNavigating: boolean;
  /** Já recarregamos para este build e o servido continua diferente (cache de borda). */
  reloadBlocked: boolean;
}

/** Busca o buildId publicado; `null` em qualquer falha (offline, 404 em dev, JSON inválido). */
export async function fetchDeployedBuildId(
  fetchImpl: typeof fetch = fetch
): Promise<string | null> {
  try {
    const response = await fetchImpl(VERSION_URL, { cache: "no-store" });
    if (!response.ok) return null;
    const body: unknown = await response.json();
    const buildId = (body as { buildId?: unknown } | null)?.buildId;
    return typeof buildId === "string" && buildId !== "" ? buildId : null;
  } catch {
    return null;
  }
}

export function decideUpdateAction(state: UpdateState): UpdateAction {
  if (!state.updatePending) return "wait";
  if (state.reloadBlocked) return "banner-only";
  if (state.isHidden) return "reload-now";
  if (state.isNavigating) return "reload-on-navigation";
  return "countdown";
}

/** Contador pausa com campo em foco ou dialog aberto: ninguém perde o que está digitando. */
export function isCountdownPaused(doc: Pick<Document, "activeElement" | "querySelector">): boolean {
  const active = doc.activeElement as HTMLElement | null;
  const isEditing =
    !!active &&
    (active.tagName === "INPUT" ||
      active.tagName === "TEXTAREA" ||
      active.isContentEditable === true);
  return isEditing || doc.querySelector("[role=dialog]") !== null;
}

// --- Anti-loop (sessionStorage; qualquer falha de storage = tratar como bloqueado) ---------------

export function hasReloadedFor(buildId: string, storage?: Pick<Storage, "getItem">): boolean {
  try {
    return (storage ?? sessionStorage).getItem(RELOADED_FOR_KEY) === buildId;
  } catch {
    // Sem storage não dá para provar que não estamos em loop: melhor só mostrar o banner.
    return true;
  }
}

export function markReloadedFor(buildId: string, storage?: Pick<Storage, "setItem">): void {
  try {
    (storage ?? sessionStorage).setItem(RELOADED_FOR_KEY, buildId);
  } catch {
    /* hasReloadedFor já falha fechado */
  }
}

/** Reserva o direito de recarregar por erro de chunk; false se já recarregamos há pouco. */
export function claimPreloadReload(
  now: number,
  storage?: Pick<Storage, "getItem" | "setItem">
): boolean {
  try {
    const store = storage ?? sessionStorage;
    const last = Number(store.getItem(PRELOAD_RELOAD_AT_KEY) ?? 0);
    if (now - last < PRELOAD_RELOAD_COOLDOWN_MS) return false;
    store.setItem(PRELOAD_RELOAD_AT_KEY, String(now));
    return true;
  } catch {
    return false;
  }
}

/**
 * Handler de `vite:preloadError`: o chunk velho já sumiu, então não há o que "tentar de novo".
 * `preventDefault` impede o Vite de relançar o erro; recarrega uma vez por janela de cooldown.
 */
export function createPreloadErrorHandler(
  reload: () => void,
  now: () => number = Date.now
): (event: Pick<Event, "preventDefault">) => void {
  return (event) => {
    event.preventDefault();
    if (claimPreloadReload(now())) reload();
  };
}

const CHUNK_ERROR_PATTERN =
  /dynamically imported module|importing a module script failed|unable to preload|loading chunk|loading css chunk/i;

/** Erro de import dinâmico (chunk 404 pós-deploy) nos vários textos de Chrome/Safari/Firefox. */
export function isChunkLoadError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return CHUNK_ERROR_PATTERN.test(message);
}
