import { useDataProvider } from "@/lib/api/context";
import { invalidateEndpointDependents } from "@/lib/api/invalidation";
import type {
  CreateRequest,
  DeleteRequest,
  ListRequest,
  PagedResponse,
  UpdateRequest,
} from "@/lib/api/types";
import type { InfiniteData, QueryClient, UseQueryOptions } from "@tanstack/react-query";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

/**
 * Lista em cache: a paginada guarda um `PagedResponse`; a infinita guarda as páginas
 * acumuladas. As duas moram sob o mesmo prefixo `[endpoint, "list"]` — de propósito, para
 * a invalidação das mutations casar nas duas — então toda cirurgia trata as duas formas.
 */
type CachedList<T> = PagedResponse<T> | InfiniteData<PagedResponse<T>>;

function isInfiniteCache<T>(data: CachedList<T>): data is InfiniteData<PagedResponse<T>> {
  return "pages" in data;
}

function rowId(row: unknown): string | number | undefined {
  return row && typeof row === "object" && "id" in row
    ? (row as { id: string | number }).id
    : undefined;
}

function mapListCaches<T>(
  queryClient: QueryClient,
  endpoint: string,
  mapPage: (page: PagedResponse<T>) => PagedResponse<T>
) {
  queryClient.setQueriesData<CachedList<T>>({ queryKey: [endpoint, "list"] }, (data) => {
    if (!data) return data;
    if (!isInfiniteCache(data)) return mapPage(data);
    return { ...data, pages: data.pages.map(mapPage) };
  });
}

/**
 * Tira a linha de toda lista em cache. Invalidar uma infinite query de 12 páginas refaz 12
 * requests EM SEQUÊNCIA; o splice custa zero request e o resultado visível é o mesmo — só a
 * última página fica com 9 itens até o próximo mount.
 */
function removeRowFromListCaches<T>(
  queryClient: QueryClient,
  endpoint: string,
  id: string | number
) {
  queryClient.setQueriesData<CachedList<T>>({ queryKey: [endpoint, "list"] }, (data) => {
    if (!data) return data;
    const drop = (page: PagedResponse<T>) => ({
      ...page,
      items: page.items.filter((row) => rowId(row) !== id),
    });
    if (!isInfiniteCache(data)) {
      const next = drop(data);
      if (next.items.length === data.items.length) return data;
      return { ...next, total: Math.max(0, data.total - 1) };
    }
    const pages = data.pages.map(drop);
    const removed = data.pages.reduce(
      (count, page, i) => count + page.items.length - pages[i].items.length,
      0
    );
    if (removed === 0) return data;
    // O `total` só é exato na página 0 (o backend só paga o COUNT em `skip === 0`) e é de lá
    // que o cabeçalho lê o contador — decrementa ali, não na página onde a linha estava.
    pages[0] = { ...pages[0], total: Math.max(0, pages[0].total - removed) };
    return { ...data, pages };
  });
}

/** Troca a linha no lugar, sem mexer na ordem nem no `total`. */
function replaceRowInListCaches<T>(
  queryClient: QueryClient,
  endpoint: string,
  id: string | number,
  row: T
) {
  mapListCaches<T>(queryClient, endpoint, (page) => {
    const index = page.items.findIndex((item) => rowId(item) === id);
    if (index < 0) return page;
    const items = [...page.items];
    items[index] = row;
    return { ...page, items };
  });
}

/**
 * Corta as infinite queries para a primeira página ANTES do invalidate — assim o refetch faz
 * 1 request em vez de N. Sob o sort padrão (`created_at DESC`) a linha nova pertence ao topo
 * de qualquer jeito, então nada do que o usuário estava vendo se perde.
 */
function truncateInfiniteLists<T>(queryClient: QueryClient, endpoint: string) {
  queryClient.setQueriesData<CachedList<T>>(
    { queryKey: [endpoint, "list", "infinite"] },
    (data) => {
      if (!data || !isInfiniteCache(data) || data.pages.length <= 1) return data;
      return { pages: data.pages.slice(0, 1), pageParams: data.pageParams.slice(0, 1) };
    }
  );
}

/**
 * Toda mutation daqui também invalida os DEPENDENTES do recurso (painel, contadores, outro
 * módulo) pelo mapa `lib/api/entity-dependencies.ts` (auditoria 2026-11-13, core-spa-02).
 * As queries do próprio `endpoint` seguem com a cirurgia de cache abaixo; recurso fora do
 * mapa é no-op.
 */
export function useCrud<T = any>(endpoint: string) {
  const { createCrudService } = useDataProvider();
  const queryClient = useQueryClient();
  // Estável por endpoint — sem `useMemo` o service vira nova instância a
  // cada render, queryFn captura nova ref, e múltiplos consumers acumulam
  // closures sobre instances diferentes.
  const service = useMemo(() => createCrudService<T>(endpoint), [createCrudService, endpoint]);

  // List query: fresh data on every visit (staleTime 0, refetchOnMount).
  // Override via optional second arg if a specific list needs longer cache.
  const useList = (
    params?: ListRequest,
    queryOptions?: Omit<UseQueryOptions<PagedResponse<T>>, "queryKey" | "queryFn">
  ) => {
    return useQuery({
      queryKey: [endpoint, "list", params],
      queryFn: () => service.list(params),
      staleTime: 0,
      refetchOnMount: "always",
      // Mantém a página anterior durante o fetch da próxima (paginação/filtro/degrau
      // de limit do EntityPicker) — sem isso a lista colapsa e o scroll volta ao topo.
      placeholderData: keepPreviousData,
      ...queryOptions,
    });
  };

  // Get single item: fresh by default (staleTime 0). Override in hooks if needed.
  const useGet = (id: string | number, enabled = true) => {
    return useQuery({
      queryKey: [endpoint, "item", id],
      queryFn: () => service.get(id),
      enabled: enabled && !!id,
      staleTime: 0,
    });
  };

  // Create mutation
  const useCreate = () => {
    return useMutation({
      mutationFn: (data: CreateRequest<T>) => service.create(data),
      onSuccess: (response, _variables) => {
        void invalidateEndpointDependents(queryClient, endpoint);
        truncateInfiniteLists<T>(queryClient, endpoint);
        queryClient.invalidateQueries({ queryKey: [endpoint, "list"] });

        // Add the new item to cache if it has an id
        if (response.data && typeof response.data === "object" && "id" in response.data) {
          queryClient.setQueryData([endpoint, "item", (response.data as any).id], response);
        }
      },
    });
  };

  // Update mutation
  const useUpdate = () => {
    return useMutation({
      mutationFn: (request: UpdateRequest<T>) => service.update(request),
      onSuccess: (response, variables) => {
        void invalidateEndpointDependents(queryClient, endpoint);
        // Update the item in cache
        queryClient.setQueryData([endpoint, "item", variables.id], response);

        // Troca a linha no lugar e marca a lista como stale SEM refetch: refazer N páginas
        // por causa de uma edição não paga. Se a edição fez a linha deixar de casar o filtro
        // atual, ela só desaparece no próximo mount — trade deliberado.
        replaceRowInListCaches<T>(queryClient, endpoint, variables.id, response.data);
        queryClient.invalidateQueries({ queryKey: [endpoint, "list"], refetchType: "none" });
      },
    });
  };

  // Replace mutation (PUT)
  const useReplace = () => {
    return useMutation({
      mutationFn: (request: UpdateRequest<T>) => service.replace(request),
      onSuccess: (response, variables) => {
        void invalidateEndpointDependents(queryClient, endpoint);
        // Update the item in cache
        queryClient.setQueryData([endpoint, "item", variables.id], response);

        replaceRowInListCaches<T>(queryClient, endpoint, variables.id, response.data);
        queryClient.invalidateQueries({ queryKey: [endpoint, "list"], refetchType: "none" });
      },
    });
  };

  // Delete mutation
  const useDelete = () => {
    return useMutation({
      mutationFn: (request: DeleteRequest) => service.delete(request),
      onSuccess: (_response, variables) => {
        void invalidateEndpointDependents(queryClient, endpoint);
        // Remove the item from cache
        queryClient.removeQueries({
          queryKey: [endpoint, "item", variables.id],
        });

        removeRowFromListCaches<T>(queryClient, endpoint, variables.id);
        // A lista paginada continua invalidando de verdade — lá a página seguinte precisa
        // puxar uma linha pra cima. A infinita já foi acertada no cache, sem request.
        queryClient.invalidateQueries({
          queryKey: [endpoint, "list"],
          predicate: (query) => query.queryKey[2] !== "infinite",
        });
      },
    });
  };

  // Bulk operations
  const useBulkCreate = () => {
    return useMutation({
      mutationFn: (items: CreateRequest<T>[]) => service.bulkCreate(items),
      onSuccess: () => {
        void invalidateEndpointDependents(queryClient, endpoint);
        // Invalidate all list queries
        queryClient.invalidateQueries({ queryKey: [endpoint, "list"] });
      },
    });
  };

  const useBulkUpdate = () => {
    return useMutation({
      mutationFn: (items: UpdateRequest<T>[]) => service.bulkUpdate(items),
      onSuccess: (_response, variables) => {
        void invalidateEndpointDependents(queryClient, endpoint);
        // Invalidate affected items and lists
        variables.forEach((item) => {
          queryClient.invalidateQueries({
            queryKey: [endpoint, "item", item.id],
          });
        });
        queryClient.invalidateQueries({ queryKey: [endpoint, "list"] });
      },
    });
  };

  const useBulkDelete = () => {
    return useMutation({
      mutationFn: (ids: (string | number)[]) => service.bulkDelete(ids),
      onSuccess: (_response, variables) => {
        void invalidateEndpointDependents(queryClient, endpoint);
        // Remove items from cache
        variables.forEach((id) => {
          queryClient.removeQueries({ queryKey: [endpoint, "item", id] });
        });

        // Invalidate list queries
        queryClient.invalidateQueries({ queryKey: [endpoint, "list"] });
      },
    });
  };

  // Custom endpoint queries and mutations
  const useCustomQuery = <R = any>(
    path: string,
    params?: Record<string, any>,
    options?: { enabled?: boolean; staleTime?: number }
  ) => {
    return useQuery({
      queryKey: [endpoint, "custom", path, params],
      queryFn: () => service.customGet<R>(path, params),
      enabled: options?.enabled ?? true,
      staleTime: options?.staleTime ?? 0,
    });
  };

  const useCustomMutation = <R = any>(
    path: string,
    method: "POST" | "PATCH" | "DELETE" = "POST"
  ) => {
    return useMutation({
      mutationFn: (data?: any) => {
        switch (method) {
          case "POST":
            return service.customPost<R>(path, data);
          case "PATCH":
            return service.customPatch<R>(path, data);
          case "DELETE":
            return service.customDelete<R>(path);
          default:
            throw new Error(`Unsupported method: ${method}`);
        }
      },
      onSuccess: () => {
        void invalidateEndpointDependents(queryClient, endpoint);
        // Invalidate related queries
        queryClient.invalidateQueries({ queryKey: [endpoint] });
      },
    });
  };

  return {
    // Queries
    useList,
    useGet,
    useCustomQuery,

    // Mutations
    useCreate,
    useUpdate,
    useReplace,
    useDelete,
    useBulkCreate,
    useBulkUpdate,
    useBulkDelete,
    useCustomMutation,

    // Direct service access for advanced use cases
    service,
  };
}
