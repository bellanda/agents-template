import {
  DEFAULT_APP_STYLE,
  LEGACY_DARK_APP_STYLE,
  findAppStyle,
  isAppStyleId,
  type AppStyleId,
} from "@/lib/appearance/app-styles";

/**
 * Estilo visual ativo, fora do React: vive em `<html data-style="…" class="light|dark">`.
 *
 * A verdade é `users.ui_preferences.app_style` (via `/accounts/me`); o localStorage é o cache que
 * pinta a primeira tela antes de a conta responder — sem ele a tela abriria clara e trocaria
 * depois. O template não tem login: a "conta" é a identidade de `useUserId`, e `setAccount`
 * recebe o resultado do `/accounts/me` (ver `useAppStyleAccountSync`).
 */
const STORAGE_KEY = "app:app-style:v1";
// Chave do `ThemeProvider` removido: lida UMA vez para quem já usava o escuro não voltar ao claro.
const LEGACY_THEME_KEY = "vite-ui-theme";
const STYLE_ATTRIBUTE = "data-style";

interface AccountSnapshot {
  userId: string;
  /** `ui_preferences.app_style` como veio do servidor (qualquer valor, inclusive inválido). */
  appStyle: unknown;
}

const listeners = new Set<() => void>();
let activeStyle: AppStyleId = DEFAULT_APP_STYLE;
let account: AccountSnapshot | null = null;
// Último valor visto NA CONTA. Só uma mudança dele reaplica: um `/accounts/me` que chega antes
// do PATCH da escolha terminar ainda traz o valor velho e não pode desfazê-la.
let lastServerStyle: unknown;
// Quem já escolheu nesta aba dispensa o dialog de boas-vindas: o `/accounts/me` só traz o valor
// novo no próximo fetch. Guarda o id, não um booleano, para outra pessoa no mesmo navegador
// ainda ver o dialog.
let chosenByUserId: string | null = null;

function notifyAll(): void {
  listeners.forEach((notify) => notify());
}

function readCachedStyle(): AppStyleId {
  try {
    const cached = localStorage.getItem(STORAGE_KEY);
    if (isAppStyleId(cached)) return cached;
    const migrated = localStorage.getItem(LEGACY_THEME_KEY) === "dark";
    // Remove sempre: a chave antiga não tem mais dono depois desta leitura.
    localStorage.removeItem(LEGACY_THEME_KEY);
    return migrated ? LEGACY_DARK_APP_STYLE : DEFAULT_APP_STYLE;
  } catch {
    return DEFAULT_APP_STYLE;
  }
}

function writeCachedStyle(id: AppStyleId): void {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // Storage bloqueado (aba anônima): o estilo vale até fechar a aba e volta pela conta.
  }
}

function paintAppStyle(id: AppStyleId): void {
  const style = findAppStyle(id);
  const root = document.documentElement;
  root.setAttribute(STYLE_ATTRIBUTE, style.id);
  root.classList.remove("light", "dark");
  root.classList.add(style.mode);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", style.themeColor);
}

/** Aplica e lembra neste navegador. Não fala com o servidor — ver `useAppStyle`. */
export function applyAppStyle(id: AppStyleId): void {
  activeStyle = id;
  paintAppStyle(id);
  writeCachedStyle(id);
  notifyAll();
}

/** Roda em `main.tsx` antes do primeiro render. */
export function bootAppStyle(): void {
  activeStyle = readCachedStyle();
  paintAppStyle(activeStyle);
  writeCachedStyle(activeStyle);
}

/** Resultado do `/accounts/me`: reaplica só quando o valor DA CONTA muda. */
export function setAccount(next: AccountSnapshot | null): void {
  account = next;
  const fromServer = next?.appStyle;
  if (fromServer !== lastServerStyle) {
    lastServerStyle = fromServer;
    if (isAppStyleId(fromServer) && fromServer !== activeStyle) {
      applyAppStyle(fromServer);
      return;
    }
  }
  notifyAll();
}

/** A pessoa escolheu de propósito (dialog, seletor do header ou link `/estilo/<id>`). */
export function markAppStyleChosen(userId: string): void {
  chosenByUserId = userId;
  notifyAll();
}

/** Conta carregada que nunca escolheu estilo: é a primeira entrada e o dialog de estilo abre. */
export function isAppStyleChoicePending(): boolean {
  if (!account || chosenByUserId === account.userId) return false;
  return !isAppStyleId(account.appStyle);
}

export function subscribeAppStyle(notify: () => void): () => void {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

export function getActiveAppStyle(): AppStyleId {
  return activeStyle;
}

/** Só para testes: volta o módulo ao estado de antes do boot. */
export function resetAppStyleStoreForTests(): void {
  listeners.clear();
  activeStyle = DEFAULT_APP_STYLE;
  account = null;
  lastServerStyle = undefined;
  chosenByUserId = null;
}
