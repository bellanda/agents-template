/**
 * Per-person font size (user decision 2026-11-09, for people who found the text too small).
 *
 * The scale goes on the `<html>` font-size: text, spacing and icons are all in `rem`, so the whole
 * screen grows together and nothing gets cramped. It only goes up: below 100% form fields would
 * drop under 16px and iOS would zoom on focus. Each id's scale lives in
 * `styles/themes/font-size.css`. A new id also goes in the backend `FontSizeId`.
 *
 * Same design as `app-style-store.ts`: the source of truth is `users.ui_preferences.font_size` and
 * localStorage is the cache that paints the first screen before `/accounts/me` answers.
 */
export const FONT_SIZES = [
  { id: "padrao", name: "Padrão" },
  { id: "grande", name: "Grande" },
  { id: "muito-grande", name: "Muito grande" },
] as const;

export type FontSizeId = (typeof FONT_SIZES)[number]["id"];

export const DEFAULT_FONT_SIZE: FontSizeId = "padrao";

const STORAGE_KEY = "app:font-size:v1";
const FONT_SIZE_ATTRIBUTE = "data-font-size";

const listeners = new Set<() => void>();
let activeSize: FontSizeId = DEFAULT_FONT_SIZE;
// Last value seen ON THE ACCOUNT. Only a change to it reapplies: an `/accounts/me` that lands
// before the PATCH finishes still carries the old value and must not undo the choice.
let lastServerSize: unknown;

export function isFontSizeId(value: unknown): value is FontSizeId {
  return FONT_SIZES.some((size) => size.id === value);
}

function readCachedSize(): FontSizeId {
  try {
    const cached = localStorage.getItem(STORAGE_KEY);
    return isFontSizeId(cached) ? cached : DEFAULT_FONT_SIZE;
  } catch {
    return DEFAULT_FONT_SIZE;
  }
}

function writeCachedSize(id: FontSizeId): void {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // Storage blocked (private tab): the size lasts until the tab closes and returns from the account.
  }
}

function paintFontSize(id: FontSizeId): void {
  document.documentElement.setAttribute(FONT_SIZE_ATTRIBUTE, id);
}

/** Applies and remembers in this browser. Never calls the server: `chooseStyle` saves it. */
export function applyFontSize(id: FontSizeId): void {
  activeSize = id;
  paintFontSize(id);
  writeCachedSize(id);
  listeners.forEach((notify) => notify());
}

/**
 * Follows the account: `setAccount` (`app-style-store.ts`) passes `ui_preferences.font_size` here
 * after every `/accounts/me`. The template has no auth store, so the value arrives as an argument.
 */
export function syncFontSizeFromAccount(fromServer: unknown): void {
  if (fromServer === lastServerSize) return;
  lastServerSize = fromServer;
  if (isFontSizeId(fromServer) && fromServer !== activeSize) applyFontSize(fromServer);
}

/** Runs in `main.tsx` before the first render; the account takes over via `syncFontSizeFromAccount`. */
export function bootFontSize(): void {
  activeSize = readCachedSize();
  paintFontSize(activeSize);
}

export function subscribeFontSize(notify: () => void): () => void {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

export function getActiveFontSize(): FontSizeId {
  return activeSize;
}
