/**
 * Captura do `beforeinstallprompt` (Android/desktop Chromium) + registro do `sw.js` no boot.
 *
 * O evento dispara UMA vez, cedo, e some se ninguém escutar — por isso o listener nasce
 * em `initInstallPrompt()` chamado no `main.tsx`, antes de qualquer componente montar.
 * Store vanilla + `useSyncExternalStore` (mesmo padrão do `authStore`): o item do menu do
 * usuário e o dialog de instruções (irmão do menu) leem o mesmo estado.
 *
 * No iOS não existe o evento: a instalação é manual (Compartilhar → Adicionar à Tela de
 * Início), então o botão abre um dialog com os passos (`instructionsOpen`).
 */
import { registerServiceWorkerAtBoot } from "@/lib/push/register-sw";
import { useSyncExternalStore } from "react";

/** Evento não padronizado (só Chromium) — fora do lib.dom do TypeScript. */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

interface InstallPromptState {
  deferredPrompt: BeforeInstallPromptEvent | null;
  instructionsOpen: boolean;
}

let state: InstallPromptState = { deferredPrompt: null, instructionsOpen: false };
const listeners = new Set<() => void>();

function setState(next: Partial<InstallPromptState>) {
  state = { ...state, ...next };
  listeners.forEach((listener) => listener());
}

let initialized = false;

/** Chamar uma vez no boot (`main.tsx`). Idempotente. */
export function initInstallPrompt(): void {
  if (initialized || typeof window === "undefined") return;
  initialized = true;

  window.addEventListener("beforeinstallprompt", (event) => {
    // Sem preventDefault o Chrome mostra a mini-infobar própria e o evento não fica reutilizável.
    event.preventDefault();
    setState({ deferredPrompt: event as BeforeInstallPromptEvent });
  });
  // Instalado (por qualquer caminho): o evento guardado já não vale.
  window.addEventListener("appinstalled", () => setState({ deferredPrompt: null }));

  // SW push-only (sem fetch handler, sem cache offline) registrado no boot: Chromium mais antigo
  // só considera o app instalável com SW ativo, e o push passa a ter o SW pronto desde o início.
  void registerServiceWorkerAtBoot();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): InstallPromptState {
  return state;
}

export function useInstallPromptState(): InstallPromptState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function openInstallInstructions(): void {
  setState({ instructionsOpen: true });
}

export function closeInstallInstructions(): void {
  setState({ instructionsOpen: false });
}

/** Dispara o prompt nativo. O evento só pode ser usado uma vez — descartamos após o uso. */
export async function promptNativeInstall(): Promise<"accepted" | "dismissed" | "unavailable"> {
  const deferred = state.deferredPrompt;
  if (!deferred) return "unavailable";
  await deferred.prompt();
  const { outcome } = await deferred.userChoice;
  setState({ deferredPrompt: null });
  return outcome;
}
