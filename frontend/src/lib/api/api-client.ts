import { getAccessToken } from "@/lib/api/access-token-store";
import { refreshSession } from "@/lib/api/client";
import { camelToSnake, objectKeysToCamelCase, objectKeysToSnakeCase } from "@/lib/utils/case";
import {
  NETWORK_ERROR_CODE,
  NETWORK_ERROR_MESSAGE,
  httpStatusFallbackMessage,
  isNetworkError,
  rawNetworkErrorMessage,
} from "./network-error";
import { ChunkUploadError, stageLargeFormFile, type ChunkTransport } from "./chunked-upload";
import type { ApiError, ApiResponse, BackendAdapter } from "./types";

/**
 * Full API client (ported from the canonical app, audit 2026-11-13 template-gap-03), for every
 * endpoint that follows the fleet's JSON contract:
 *   - Bearer from the in-memory token store (falls back to `fallbackToken`, the open-identity
 *     stub of local/test: the template backend resolves a bearer AS the user id);
 *   - ONE refresh-and-retry on 401 through `refreshSession` of `client.ts` — the same single-flight
 *     `apiFetch` uses, so the app registers its renewal once (`registerSessionRefresher`);
 *   - request keys camelCase -> snake_case, response keys snake_case -> camelCase (`getRaw` opts out);
 *   - errors thrown as `ApiError` (adapter-normalised, with the `X-Request-ID` for the backend log);
 *   - `upload()` over XMLHttpRequest, the only transport with REAL upload progress.
 * `apiFetch` (client.ts) stays for callers that need the raw `Response` (streaming, SSE, blobs).
 */

/** Header the backend request-logging middleware echoes on every response. */
const REQUEST_ID_HEADER = "x-request-id";

/** Never shown on screen: `isNetworkError` keys on the `TypeError` class. */
const XHR_TRANSPORT_FAILURE = "XMLHttpRequest transport failure";

/** PUT exists for "replace the single instance" routes; `ApiClient.put` JSON-stringifies, so it never carries a FormData. */
type UploadMethod = "POST" | "PUT";

interface MultipartResult {
  status: number;
  ok: boolean;
  data: unknown;
  requestId: string | null;
}

type QueryParams = Record<string, string | number | boolean | undefined>;

/**
 * One multipart request over XMLHttpRequest. Resolves with the HTTP status for ANY response (the
 * caller decides about 401/refresh); rejects with a `TypeError` (same class `fetch` throws) when
 * the request never got a verdict (offline, DNS, server down, CORS).
 */
function sendMultipart(
  url: string,
  body: FormData | Blob,
  accessToken: string | null,
  method: UploadMethod,
  onProgress?: (percent: number) => void,
  chunk?: { onBytes?: (loaded: number) => void }
): Promise<MultipartResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url);
    xhr.withCredentials = true;
    xhr.responseType = "text";
    if (accessToken) xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
    // Multipart: no Content-Type on purpose, the browser must generate it WITH the boundary.
    // Raw chunk (chunked-upload.ts): octet-stream.
    if (chunk) xhr.setRequestHeader("Content-Type", "application/octet-stream");

    let lastPercent = -1;
    xhr.upload.onprogress = (event) => {
      if (chunk?.onBytes) chunk.onBytes(event.loaded);
      if (!onProgress || !event.lengthComputable || event.total === 0) return;
      const percent = Math.min(100, Math.round((event.loaded / event.total) * 100));
      // Progress events fire many times per percent: only forward real changes.
      if (percent === lastPercent) return;
      lastPercent = percent;
      onProgress(percent);
    };

    xhr.onload = () => {
      const contentType = xhr.getResponseHeader("content-type") ?? "";
      try {
        const text = xhr.responseText;
        const data = contentType.includes("application/json")
          ? text
            ? JSON.parse(text)
            : null
          : text || null;
        resolve({
          status: xhr.status,
          ok: xhr.status >= 200 && xhr.status < 300,
          data,
          requestId: xhr.getResponseHeader(REQUEST_ID_HEADER),
        });
      } catch (error) {
        reject(error);
      }
    };
    const transportFailure = () => reject(new TypeError(XHR_TRANSPORT_FAILURE));
    xhr.onerror = transportFailure;
    xhr.onabort = transportFailure;
    xhr.ontimeout = transportFailure;

    xhr.send(body);
  });
}

export interface ApiClientOptions {
  /** Open-identity stub (local/test): sent as the bearer when no session token exists. */
  fallbackToken?: () => string | null | undefined;
}

export class ApiClient {
  private adapter: BackendAdapter;
  private fallbackToken: () => string | null | undefined;

  constructor(adapter: BackendAdapter, options: ApiClientOptions = {}) {
    this.adapter = adapter;
    this.fallbackToken = options.fallbackToken ?? (() => null);
  }

  private currentToken(): string | null {
    return getAccessToken() ?? this.fallbackToken() ?? null;
  }

  private async request<T = any>(
    url: string,
    options: RequestInit = {},
    meta: { skipCaseTransform?: boolean } = {}
  ): Promise<ApiResponse<T>> {
    const fullUrl = `${this.adapter.baseURL}${url}`;
    let body = options.body;

    const isURLSearchParams = body instanceof URLSearchParams;
    if (isURLSearchParams && body) body = body.toString();

    const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
    if (isURLSearchParams) {
      if (!headers["Content-Type"]) headers["Content-Type"] = "application/x-www-form-urlencoded";
    } else if (body instanceof FormData) {
      // No Content-Type: the browser adds the multipart boundary.
    } else if (body !== null && body !== undefined) {
      if (!headers["Content-Type"]) headers["Content-Type"] = "application/json";
    }

    const accessToken = this.currentToken();
    if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

    if (body && typeof body === "string") {
      try {
        let transformed = objectKeysToSnakeCase(JSON.parse(body));
        if (this.adapter.transformRequest) transformed = this.adapter.transformRequest(transformed);
        body = JSON.stringify(transformed);
      } catch {
        // Not JSON (form-urlencoded string): keep the original body.
      }
    }

    // Id of the LAST response seen, so a thrown `ApiError` points at the backend log line.
    let requestId: string | null = null;
    try {
      const send = () =>
        fetch(fullUrl, { ...options, headers, body, credentials: "include", mode: "cors" });
      let response = await send();

      if (response.status === 401 && (await refreshSession())) {
        const renewed = this.currentToken();
        if (renewed) {
          headers["Authorization"] = `Bearer ${renewed}`;
          response = await send();
        }
      }

      requestId = response.headers.get(REQUEST_ID_HEADER);
      const contentType = response.headers.get("content-type");
      // A 204 still carries `content-type: application/json` with an empty body.
      const text = await response.text();
      const data = !text
        ? null
        : contentType?.includes("application/json")
          ? JSON.parse(text)
          : text;
      return this.settleResponse<T>(response.status, response.ok, data, meta);
    } catch (error: any) {
      throw this.toApiError(error, requestId);
    }
  }

  /** Non-2xx -> thrown `ApiError`; 2xx -> payload with keys renamed to camelCase. */
  private settleResponse<T>(
    status: number,
    ok: boolean,
    data: unknown,
    meta: { skipCaseTransform?: boolean }
  ): ApiResponse<T> {
    if (!ok) {
      const failure = { response: { status, data } };
      throw this.adapter.transformError
        ? this.adapter.transformError(failure)
        : this.defaultErrorTransform(failure);
    }
    const payload =
      !meta.skipCaseTransform && data && typeof data === "object"
        ? objectKeysToCamelCase(data)
        : data;
    return { data: payload as T, success: true, status };
  }

  /** Already-normalised `ApiError`s (they carry a `status`) pass through; a transport `TypeError` is normalised here. */
  private toApiError(error: any, requestId: string | null = null): ApiError {
    const apiError: ApiError = error.status
      ? error
      : this.adapter.transformError
        ? this.adapter.transformError(error)
        : this.defaultErrorTransform(error);
    if (requestId && !apiError.requestId) apiError.requestId = requestId;
    return apiError;
  }

  private defaultErrorTransform(error: any): ApiError {
    if (error.response) {
      return {
        // `detail` before `message`: it is the key the backend uses (RFC 7807).
        message:
          error.response.data?.detail ||
          error.response.data?.message ||
          httpStatusFallbackMessage(error.response.status),
        status: error.response.status,
        code: error.response.data?.code,
        details: error.response.data?.details,
      };
    }
    if (isNetworkError(error)) {
      return {
        message: NETWORK_ERROR_MESSAGE,
        status: 0,
        code: NETWORK_ERROR_CODE,
        details: { originalError: rawNetworkErrorMessage(error) },
      };
    }
    return {
      message: error.message || "Erro inesperado. Tente novamente.",
      status: 0,
      code: "UNKNOWN_ERROR",
    };
  }

  private buildUrlWithParams(url: string, params?: QueryParams): string {
    if (!params || Object.keys(params).length === 0) return url;
    const snakeParams: Record<string, string> = {};
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") snakeParams[camelToSnake(k)] = String(v);
    }
    const query = new URLSearchParams(snakeParams).toString();
    return query ? `${url}${url.includes("?") ? "&" : "?"}${query}` : url;
  }

  async get<T = any>(url: string, config?: { params?: QueryParams }): Promise<ApiResponse<T>> {
    return this.request<T>(this.buildUrlWithParams(url, config?.params), { method: "GET" });
  }

  /** Like `get()` but keeps the upstream snake_case keys (the caller maps the payload itself). */
  async getRaw<T = any>(url: string, config?: { params?: QueryParams }): Promise<ApiResponse<T>> {
    return this.request<T>(
      this.buildUrlWithParams(url, config?.params),
      { method: "GET" },
      { skipCaseTransform: true }
    );
  }

  /**
   * Binary download behind the Bearer (`request()` reads non-JSON as text, which would corrupt the
   * file). `same-origin`, not `include`: the Bearer authenticates, and a private object-storage
   * file comes back as a 302 to a signed bucket URL that would otherwise need CORS credentials.
   */
  async getBlob(url: string): Promise<Blob> {
    const send = () => {
      const token = this.currentToken();
      return fetch(`${this.adapter.baseURL}${url}`, {
        method: "GET",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "same-origin",
        mode: "cors",
      });
    };
    let response = await send();
    if (response.status === 401 && (await refreshSession())) response = await send();
    if (!response.ok) {
      throw this.defaultErrorTransform({
        response: { status: response.status, data: await response.text() },
      });
    }
    return response.blob();
  }

  /**
   * Multipart upload with REAL progress (XMLHttpRequest). Same contract as `request()`: Bearer,
   * ONE refresh-and-retry on 401, transport failure -> NETWORK_ERROR (status 0), camelCased JSON.
   * `onProgress` gets an integer 0-100 of the BODY sent: 100 means "bytes are on the wire", not
   * "server finished" (the UI should switch to an indeterminate "Processando..."). After a 401 +
   * refresh the body is sent again and progress restarts from 0.
   *
   * Chunked staging (decision 2026-11-16): a `file` field above 8 MiB is first sent in chunks
   * to `/upload-sessions` (`chunked-upload.ts`) and the endpoint receives `file_upload_id`
   * instead, so every request stays under nginx's 20 MB. `direct: true` skips that (PUBLIC,
   * unauthenticated call sites: the session endpoints need auth) and the file must then fit
   * `DIRECT_MAX_BYTES`. During staging `onProgress` tracks chunk bytes; the tiny final request
   * is reported as 100.
   */
  async upload<T = any>(
    url: string,
    form: FormData,
    options: {
      method?: UploadMethod;
      onProgress?: (percent: number) => void;
      direct?: boolean;
      signal?: AbortSignal;
    } = {}
  ): Promise<ApiResponse<T>> {
    const fullUrl = `${this.adapter.baseURL}${url}`;
    const method = options.method ?? "POST";
    let requestId: string | null = null;
    let body = form;
    try {
      if (!options.direct) {
        body = await stageLargeFormFile(form, this.chunkTransport(), {
          signal: options.signal,
          onProgress: (sent, total) =>
            options.onProgress?.(Math.min(99, Math.floor((sent / total) * 100))),
        });
        if (body !== form) options.onProgress?.(100);
      }
      const onFinalProgress = body === form ? options.onProgress : undefined;
      let response = await sendMultipart(
        fullUrl,
        body,
        this.currentToken(),
        method,
        onFinalProgress
      );
      if (response.status === 401 && (await refreshSession())) {
        const renewed = this.currentToken();
        if (renewed) {
          onFinalProgress?.(0);
          response = await sendMultipart(fullUrl, body, renewed, method, onFinalProgress);
        }
      }
      requestId = response.requestId;
      return this.settleResponse<T>(response.status, response.ok, response.data, {});
    } catch (error: any) {
      throw this.toApiError(this.mapChunkError(error), requestId);
    }
  }

  /** Session creation / chunk verdicts (413 too big, 429 too many open sessions, 4xx) become
   * ordinary `ApiError`s, so the caller maps them like any other upload failure. */
  private mapChunkError(error: any): any {
    if (!(error instanceof ChunkUploadError)) return error;
    const failure = { response: { status: error.status, data: { detail: error.message } } };
    return this.adapter.transformError
      ? this.adapter.transformError(failure)
      : this.defaultErrorTransform(failure);
  }

  /**
   * Transport for `chunked-upload.ts` built on this client's own auth: JSON through `request()`
   * (Bearer + refresh-on-401, raw snake_case body, no camelCase on the reply), chunk PUT through
   * XHR for byte progress with one refresh-and-retry on 401. Both resolve for any HTTP status and
   * reject only when no verdict arrived (network).
   */
  chunkTransport(): ChunkTransport {
    return {
      json: async (method, path, body) => {
        try {
          const res = await this.request(
            path,
            { method, body: body === undefined ? undefined : JSON.stringify(body) },
            { skipCaseTransform: true }
          );
          return { status: res.status ?? 200, body: res.data };
        } catch (error: any) {
          // status 0 = NETWORK_ERROR: no verdict, let the caller retry.
          if (!error?.status) throw error;
          return { status: error.status, body: { detail: error.message } };
        }
      },
      putChunk: async (path, chunk, onBytes) => {
        const fullUrl = `${this.adapter.baseURL}${path}`;
        let response = await sendMultipart(fullUrl, chunk, this.currentToken(), "PUT", undefined, {
          onBytes,
        });
        if (response.status === 401 && (await refreshSession())) {
          response = await sendMultipart(fullUrl, chunk, this.currentToken(), "PUT", undefined, {
            onBytes,
          });
        }
        return { status: response.status, body: response.data };
      },
    };
  }

  async post<T = any>(
    url: string,
    data?: any,
    config?: RequestInit & { params?: QueryParams }
  ): Promise<ApiResponse<T>> {
    let body: any;
    if (data instanceof URLSearchParams || data instanceof FormData) body = data;
    else if (data) body = JSON.stringify(data);
    const { params, ...init } = config ?? {};
    return this.request<T>(this.buildUrlWithParams(url, params), { method: "POST", body, ...init });
  }

  async put<T = any>(
    url: string,
    data?: any,
    config?: RequestInit & { params?: QueryParams }
  ): Promise<ApiResponse<T>> {
    const { params, ...init } = config ?? {};
    return this.request<T>(this.buildUrlWithParams(url, params), {
      method: "PUT",
      body: data ? JSON.stringify(data) : undefined,
      ...init,
    });
  }

  async patch<T = any>(
    url: string,
    data?: any,
    config?: RequestInit & { params?: QueryParams }
  ): Promise<ApiResponse<T>> {
    const { params, ...init } = config ?? {};
    return this.request<T>(this.buildUrlWithParams(url, params), {
      method: "PATCH",
      body: data ? JSON.stringify(data) : undefined,
      ...init,
    });
  }

  async delete<T = any>(
    url: string,
    config?: RequestInit & { data?: any; params?: QueryParams }
  ): Promise<ApiResponse<T>> {
    const { params, data, ...init } = config ?? {};
    return this.request<T>(this.buildUrlWithParams(url, params), {
      method: "DELETE",
      body: data ? JSON.stringify(data) : undefined,
      ...init,
    });
  }
}
