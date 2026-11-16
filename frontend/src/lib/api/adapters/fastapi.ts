/** Base path of the backend API (same-origin behind the reverse proxy; override per environment). */
const API_URL: string = import.meta.env.VITE_API_URL ?? "/api/v1";
import {
  NETWORK_ERROR_CODE,
  NETWORK_ERROR_MESSAGE,
  httpStatusFallbackMessage,
  rawNetworkErrorMessage,
} from "../network-error";
import type { ApiError, AuthTokens, BackendAdapter } from "../types";

export const fastApiAdapter: BackendAdapter = {
  name: "FastAPI",
  baseURL: API_URL,

  // FastAPI expects standard JSON — no transformation needed.
  transformRequest: (data: unknown) => data,

  // Normalize FastAPI error shapes into ApiError.
  // Do NOT reshape response data here — that belongs in query functions.
  transformError: (error: unknown): ApiError => {
    if (
      error &&
      typeof error === "object" &&
      "response" in error &&
      error.response &&
      typeof error.response === "object" &&
      "status" in error.response
    ) {
      const response = error.response as { status: number; data?: unknown };
      const { status, data } = response;

      // Pydantic validation errors (422)
      if (status === 422 && data && typeof data === "object" && "detail" in data) {
        const details: Record<string, string[]> = {};
        let message = "Validation error";
        const dataWithDetail = data as { detail?: unknown };

        if (Array.isArray(dataWithDetail.detail)) {
          const detailArray = dataWithDetail.detail as Array<{
            loc?: (string | number)[];
            msg?: string;
          }>;
          detailArray.forEach((err) => {
            const field = err.loc?.join(".") || "unknown";
            if (!details[field]) details[field] = [];
            if (err.msg) details[field].push(err.msg);
          });
          if (detailArray.length > 0 && detailArray[0]?.msg) message = detailArray[0].msg;
        }

        return { message, status, code: "VALIDATION_ERROR", details };
      }

      if (status === 401) {
        const msg =
          data &&
          typeof data === "object" &&
          "detail" in data &&
          typeof (data as { detail?: unknown }).detail === "string"
            ? (data as { detail: string }).detail
            : "Authentication required";
        return { message: msg, status, code: "AUTHENTICATION_ERROR" };
      }

      if (status === 403) {
        const msg =
          data &&
          typeof data === "object" &&
          "detail" in data &&
          typeof (data as { detail?: unknown }).detail === "string"
            ? (data as { detail: string }).detail
            : "Permission denied";
        return { message: msg, status, code: "PERMISSION_ERROR" };
      }

      if (status === 404) {
        const msg =
          data &&
          typeof data === "object" &&
          "detail" in data &&
          typeof (data as { detail?: unknown }).detail === "string"
            ? (data as { detail: string }).detail
            : "Resource not found";
        return { message: msg, status, code: "NOT_FOUND" };
      }

      const fallbackMsg =
        data &&
        typeof data === "object" &&
        "detail" in data &&
        typeof (data as { detail?: unknown }).detail === "string"
          ? (data as { detail: string }).detail
          : data &&
              typeof data === "object" &&
              "message" in data &&
              typeof (data as { message?: unknown }).message === "string"
            ? (data as { message: string }).message
            : httpStatusFallbackMessage(status);

      return { message: fallbackMsg, status, details: data as Record<string, unknown> };
    }

    return {
      message: NETWORK_ERROR_MESSAGE,
      status: 0,
      code: NETWORK_ERROR_CODE,
      details: { originalError: rawNetworkErrorMessage(error) },
    };
  },

  getAuthHeaders: (tokens?: AuthTokens): Record<string, string> => {
    if (!tokens) return {};
    return { Authorization: `Bearer ${tokens.accessToken}` };
  },
};
