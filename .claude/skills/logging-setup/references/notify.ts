import { toast } from "sonner";
import {
  type ClientLogKind,
  markErrorReported,
  reportClientError,
} from "@/lib/observability/client-logger";
import { errorMessage, isSessionError } from "./error-message";
import { isNetworkFailure } from "./network-error";

/**
 * O ÚNICO caminho de toast de erro do app (padrão da frota, 2026-10-22).
 *
 * Formato fixo, escolhido pelo usuário: título com a AÇÃO que falhou ("Não foi possível
 * iniciar a autorização") + descrição com o MOTIVO (`errorMessage`, que vem do backend).
 *
 * Por que existe: o toast global da `MutationCache` roda ANTES do `catch` da tela, e a tela que
 * também mostrava o erro gerava dois toasts para uma falha (Portais → "Autorizar", 2026-10-22).
 * Aqui cada objeto de erro ganha um id de toast estável: quando a tela chama `notifyError` para
 * um erro que o global já mostrou, o sonner SUBSTITUI o toast (mesmo id) — sobra um, com o
 * título mais específico. Todo erro mostrado também vai para o log do backend.
 */

export const FALLBACK_ERROR_TITLE = "Não foi possível concluir a ação";
export const FALLBACK_QUERY_ERROR_TITLE = "Não foi possível carregar os dados";
/** Prefixo do `request_id` mostrado em erro 5xx: o suporte acha a linha do backend por ele. */
const SUPPORT_CODE_LENGTH = 8;
const SERVER_ERROR_STATUS = 500;

const toastIdByError = new WeakMap<object, string>();
let nextToastId = 0;

interface ErrorFields {
  status?: number;
  requestId?: string;
  stack?: string;
}

function errorFields(error: unknown): ErrorFields {
  if (typeof error !== "object" || error === null) return {};
  const { status, requestId, stack } = error as Record<string, unknown>;
  return {
    status: typeof status === "number" ? status : undefined,
    requestId: typeof requestId === "string" ? requestId : undefined,
    stack: typeof stack === "string" ? stack : undefined,
  };
}

/** Id estável por objeto de erro; `undefined` para erro primitivo (string de validação). */
function toastIdFor(error: unknown): { id?: string; isNew: boolean } {
  if (typeof error !== "object" || error === null) return { isNew: true };
  const existing = toastIdByError.get(error);
  if (existing) return { id: existing, isNew: false };
  nextToastId += 1;
  const id = `error-${nextToastId}`;
  toastIdByError.set(error, id);
  return { id, isNew: true };
}

/** Motivo pt-BR; erro de servidor ganha o código curto do `request_id`. */
export function errorDescription(error: unknown): string {
  if (typeof error === "string") return error;
  const message = errorMessage(error);
  const { status, requestId } = errorFields(error);
  if (requestId && status !== undefined && status >= SERVER_ERROR_STATUS) {
    return `${message} (código ${requestId.slice(0, SUPPORT_CODE_LENGTH)})`;
  }
  return message;
}

function logKindFor(error: unknown): ClientLogKind {
  if (isNetworkFailure(error)) return "network";
  return errorFields(error).status ? "api_error" : "toast";
}

interface NotifyErrorOptions {
  /** Id fixo (ex.: por query) para polling que falha não empilhar toasts. */
  id?: string;
  /** Motivo próprio da tela (ex.: `UploadError.fromUnknown(err).message`). Passe o erro ORIGINAL
   *  em `error` — um objeto novo teria outro id e o toast do global não seria substituído. */
  description?: string;
}

/**
 * Mostra o erro (título da ação + motivo) e manda para o log do backend.
 *
 * `error` pode ser o erro capturado (ApiError, TypeError…) ou uma frase pronta para validação
 * local ("Escolha ao menos uma foto"). 401 fica calado: é o fluxo de sessão.
 */
export function notifyError(title: string, error: unknown, options: NotifyErrorOptions = {}): void {
  if (isSessionError(error)) return;
  const tracked = toastIdFor(error);
  const id = options.id ?? tracked.id;
  const description = options.description ?? errorDescription(error);
  toast.error(title, id ? { id, description } : { description });
  // Substituição do toast global pela tela: o erro já foi para o log na primeira vez.
  if (!tracked.isNew) return;
  markErrorReported(error);
  const { status, requestId, stack } = errorFields(error);
  reportClientError({
    kind: logKindFor(error),
    title,
    message: description,
    status,
    requestId,
    stack,
  });
}

/** Aviso amarelo: algo não saiu como esperado, mas nada falhou (ex.: parte dos itens ignorada). */
export function notifyWarning(title: string, description?: string): void {
  toast.warning(title, description ? { description } : undefined);
  reportClientError({ level: "warning", kind: "toast", title, message: description ?? title });
}

/** Sucesso verde, no mesmo formato título + descrição opcional. */
export function notifySuccess(title: string, description?: string): void {
  toast.success(title, description ? { description } : undefined);
}
