/**
 * Falha de rede tem UMA mensagem, em pt-BR, em todo o app.
 *
 * O `fetch` rejeita com `TypeError` em qualquer falha de transporte (offline,
 * DNS, servidor fora, CORS), mas o texto muda por browser — "Failed to fetch"
 * no Chromium, "Load failed" no WebKit/iOS, "NetworkError when attempting to
 * fetch resource" no Firefox. Casar por texto deixava o iPhone cair no ramo
 * genérico: o usuário via "Load failed" e o erro nem chegava como NETWORK_ERROR.
 */
export const NETWORK_ERROR_MESSAGE =
  "Sem conexão com o servidor. Verifique sua internet e tente novamente.";

/** `code` do `ApiError` já normalizado — é por ele que quem está acima do client reconhece. */
export const NETWORK_ERROR_CODE = "NETWORK_ERROR";

export function isNetworkError(error: unknown): boolean {
  return error instanceof TypeError;
}

/** Falha de rede vista de CIMA do `ApiClient`, onde o erro já virou `ApiError`.
 *  Aceita as duas formas porque o mesmo caminho recebe o `TypeError` cru do
 *  `fetch` (chamada direta) e o objeto normalizado (chamada via serviço). */
export function isNetworkFailure(error: unknown): boolean {
  if (isNetworkError(error)) return true;
  return (
    typeof error === "object" &&
    error !== null &&
    (error as { code?: unknown }).code === NETWORK_ERROR_CODE
  );
}

/** Mensagem crua do browser — vai só para `details`, nunca para a tela. */
export function rawNetworkErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
