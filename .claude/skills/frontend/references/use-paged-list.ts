import { useDataProvider } from "@/lib/api/context";
import type { ListRequest } from "@/lib/api/types";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

/** Tabela: 20 linhas cabem numa tela de notebook sem virar rolagem longa. */
export const LIST_PAGE_SIZE = 20;
/** Grade de cards: 24 fecha linhas inteiras em 2, 3 e 4 colunas. */
export const GRID_PAGE_SIZE = 24;

export type PagedListParams = Omit<ListRequest, "page" | "skip" | "limit">;

const NO_ITEMS: never[] = [];

/**
 * Página numerada sobre o MESMO `CrudService.list`. É o desvio do Kailos ao scroll
 * infinito (ver `.claude/rules/project.md`): quem usa a loja pediu página + total.
 *
 * A query key mantém o prefixo `[endpoint, "list"]` — é ele que as mutations do
 * `useCrud` invalidam. `page` vem da URL (o chamador é dono), então F5 e link
 * compartilhado abrem a mesma página; o backend devolve o total exato em toda página.
 */
export function usePagedList<T = unknown>(
  endpoint: string,
  params: PagedListParams | undefined,
  options: { page: number; pageSize?: number; enabled?: boolean }
) {
  const { createCrudService } = useDataProvider();
  // Estável por endpoint — sem isto a queryFn captura uma instância nova a cada render.
  const service = useMemo(() => createCrudService<T>(endpoint), [createCrudService, endpoint]);
  const pageSize = options.pageSize ?? LIST_PAGE_SIZE;
  const page = Math.max(1, Math.floor(options.page) || 1);

  const query = useQuery({
    queryKey: [endpoint, "list", "paged", { ...params, page, limit: pageSize }],
    queryFn: () => service.list({ ...params, skip: (page - 1) * pageSize, limit: pageSize }),
    enabled: options.enabled ?? true,
    // Voltar do detalhe para a lista não refaz a página; o frescor pós-mutation vem da
    // invalidação, que ignora staleTime.
    staleTime: 30_000,
    // A página anterior fica na tela (escurecida pelo DataList) até a próxima chegar —
    // sem isto a lista colapsa num skeleton a cada clique de página.
    placeholderData: keepPreviousData,
  });

  const items = query.data?.items ?? (NO_ITEMS as T[]);
  const total = query.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return { ...query, items, total, page, pageSize, pageCount };
}
