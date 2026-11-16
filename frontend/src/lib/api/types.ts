// Base types for API responses and requests

/** Wrapper returned by ApiClient for every successful request. */
export interface ApiResponse<T = unknown> {
  data: T;
  status: number;
  success: boolean; // always true — errors are thrown, never returned
}

/**
 * Standard paginated list response — all list endpoints must follow this shape.
 * Backend: { items: T[], total: int, skip: int, limit: int, has_more: bool }
 * Frontend: same keys, values camelCased by ApiClient.
 */
export interface PagedResponse<T = unknown> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
  /**
   * Exato — vem da sentinela `LIMIT limit+1` do backend. Opcional só como dobradiça de
   * migração: tela apontada para endpoint ainda não migrado cai no fallback
   * `skip + items.length < total`. `total` é exato apenas em `skip === 0`.
   */
  hasMore?: boolean;
}

export interface ApiError {
  message: string;
  status: number;
  code?: string;
  details?: Record<string, unknown>;
  /** `X-Request-ID` of the failed response — the key to find the backend log line. */
  requestId?: string;
}

/**
 * Tokens stored client-side. Refresh token is NEVER stored - it lives in HttpOnly cookie only.
 */
export interface AuthTokens {
  accessToken: string;
  tokenType: string;
  expiresIn: number;
}

// Generic CRUD types
export interface CreateRequest<T = unknown> {
  data: Partial<T>;
}

export interface UpdateRequest<T = unknown> {
  id: string | number;
  data: Partial<T>;
}

export interface DeleteRequest {
  id: string | number;
}

export interface ListRequest {
  page?: number;
  skip?: number;
  limit?: number;
  search?: string;
  filters?: Record<string, unknown>;
  sort?: string;
  order?: "asc" | "desc";
}

/**
 * Backend adapter interface.
 *
 * Responsibilities:
 *   - baseURL: where to send requests
 *   - getAuthHeaders: inject Authorization header
 *   - transformError: normalize backend-specific error shapes into ApiError
 *   - transformRequest: (optional) request body serialization for specific backends
 *
 * NEVER add transformResponse — reshaping response data belongs in query functions.
 * The ApiClient always returns ApiResponse<T> where T is the exact camelCased JSON.
 */
export interface BackendAdapter {
  name: string;
  baseURL: string;
  transformRequest?: (data: unknown) => unknown;
  transformError?: (error: unknown) => ApiError;
  getAuthHeaders?: (tokens?: AuthTokens) => Record<string, string>;
}
