import { UploadError } from "@/lib/api";
import { isNetworkFailure, NETWORK_ERROR_MESSAGE } from "./network-error";

/**
 * Uma frase pt-BR para QUALQUER erro que chegue à tela (padrão da frota, 2026-10-22).
 *
 * O backend manda `detail` útil (o helper de `lib/api.ts` já o põe em `Error.message`);
 * o trabalho aqui é não jogá-lo fora e dar frase própria a queda de rede e a 401/403.
 */
export const SESSION_EXPIRED_MESSAGE = "Sessão expirada. Faça login novamente.";
export const FORBIDDEN_FALLBACK_MESSAGE = "Acesso negado: você não tem permissão para esta ação.";
export const UNKNOWN_ERROR_MESSAGE = "Erro inesperado. Tente novamente.";

interface ErrorLike {
  message?: unknown;
  status?: unknown;
}

function asErrorLike(error: unknown): ErrorLike {
  return typeof error === "object" && error !== null ? (error as ErrorLike) : {};
}

function detailOf(error: unknown): string {
  const { message } = asErrorLike(error);
  return typeof message === "string" ? message.trim() : "";
}

export function errorMessage(error: unknown): string {
  if (error instanceof UploadError) return error.message;
  if (isNetworkFailure(error)) return NETWORK_ERROR_MESSAGE;

  const { status } = asErrorLike(error);
  if (status === 0) return NETWORK_ERROR_MESSAGE;
  if (status === 401) return SESSION_EXPIRED_MESSAGE;
  if (status === 403) return detailOf(error) || FORBIDDEN_FALLBACK_MESSAGE;
  return detailOf(error) || UNKNOWN_ERROR_MESSAGE;
}

/** Erro que o fluxo de sessão trata sozinho (o template não tem auth; apps com auth usam). */
export function isSessionError(error: unknown): boolean {
  return asErrorLike(error).status === 401;
}
