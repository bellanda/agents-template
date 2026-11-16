import type { ApiClient } from "@/lib/api/api-client";
import { camelToSnake } from "@/lib/utils/case";
import type {
  ApiResponse,
  CreateRequest,
  DeleteRequest,
  ListRequest,
  PagedResponse,
  UpdateRequest,
} from "@/lib/api/types";

export class CrudService<T = any> {
  constructor(
    private client: ApiClient,
    private endpoint: string
  ) {
    this.endpoint = this.normalizeEndpoint(endpoint);
  }

  private normalizeEndpoint(url: string): string {
    if (!url.startsWith("/")) url = "/" + url;
    if (url !== "/" && url.endsWith("/")) url = url.slice(0, -1);
    return url;
  }

  /**
   * List resources. Backend must return PagedResponse<T>: { items, total, skip, limit }.
   * Returns the response data directly — no shape detection needed.
   */
  async list(params?: ListRequest): Promise<PagedResponse<T>> {
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.append("page", params.page.toString());
    if (params?.skip !== undefined) queryParams.append("skip", params.skip.toString());
    if (params?.limit) queryParams.append("limit", params.limit.toString());
    if (params?.search) queryParams.append("search", params.search);
    if (params?.sort) queryParams.append("sort", params.sort);
    if (params?.order) queryParams.append("order", params.order);
    if (params?.filters) {
      // O app fala camelCase, mas o FastAPI declara os filtros em snake_case e descarta em
      // silêncio o parâmetro que não bate — foi assim que `underWarranty` nunca filtrou nada.
      // Idempotente para chave que já vem em snake.
      Object.entries(params.filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null)
          queryParams.append(camelToSnake(key), value.toString());
      });
    }
    const url = queryParams.toString()
      ? `${this.endpoint}?${queryParams.toString()}`
      : this.endpoint;
    const response = await this.client.get<PagedResponse<T>>(url);
    return response.data;
  }

  async get(id: string | number): Promise<ApiResponse<T>> {
    return this.client.get<T>(`${this.endpoint}/${id}`);
  }

  async create(data: CreateRequest<T>): Promise<ApiResponse<T>> {
    return this.client.post<T>(this.endpoint, data.data);
  }

  async update(request: UpdateRequest<T>): Promise<ApiResponse<T>> {
    return this.client.patch<T>(`${this.endpoint}/${request.id}`, request.data);
  }

  async replace(request: UpdateRequest<T>): Promise<ApiResponse<T>> {
    return this.client.put<T>(`${this.endpoint}/${request.id}`, request.data);
  }

  async delete(request: DeleteRequest): Promise<ApiResponse<void>> {
    return this.client.delete(`${this.endpoint}/${request.id}`);
  }

  async bulkCreate(items: CreateRequest<T>[]): Promise<ApiResponse<T[]>> {
    return this.client.post<T[]>(
      `${this.endpoint}/bulk`,
      items.map((i) => i.data)
    );
  }

  async bulkUpdate(items: UpdateRequest<T>[]): Promise<ApiResponse<T[]>> {
    return this.client.patch<T[]>(`${this.endpoint}/bulk`, items);
  }

  async bulkDelete(ids: (string | number)[]): Promise<ApiResponse<void>> {
    return this.client.delete(`${this.endpoint}/bulk`, { data: { ids } });
  }

  private normalizePath(path: string): string {
    return path.startsWith("/") ? path.slice(1) : path;
  }

  async customGet<R = any>(path: string, params?: Record<string, any>): Promise<ApiResponse<R>> {
    const p = this.normalizePath(path);
    const qs = params ? new URLSearchParams(params).toString() : "";
    return this.client.get<R>(qs ? `${this.endpoint}/${p}?${qs}` : `${this.endpoint}/${p}`);
  }

  async customPost<R = any>(path: string, data?: any): Promise<ApiResponse<R>> {
    return this.client.post<R>(`${this.endpoint}/${this.normalizePath(path)}`, data);
  }

  async customPatch<R = any>(path: string, data?: any): Promise<ApiResponse<R>> {
    return this.client.patch<R>(`${this.endpoint}/${this.normalizePath(path)}`, data);
  }

  async customDelete<R = any>(path: string): Promise<ApiResponse<R>> {
    return this.client.delete<R>(`${this.endpoint}/${this.normalizePath(path)}`);
  }
}
