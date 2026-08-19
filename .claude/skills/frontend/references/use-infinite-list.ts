import { useDataProvider } from "@/lib/api/context";
import type { ListRequest, PagedResponse } from "@/lib/api/types";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

/** 10 por vez: com ORDER BY indexado e sentinela LIMIT+1, cada degrau é barato. */
export const LIST_PAGE_SIZE = 10;

/**
 * Distância do fim que dispara a próxima página. ~4 cards — busca antes do
 * usuário chegar no fim, sem pré-carregar página que ele nunca veria. Abaixo de
 * ~200px o spinner aparece.
 */
const SENTINEL_ROOT_MARGIN = "400px 0px";

export type InfiniteListParams = Omit<ListRequest, "page" | "skip" | "limit">;

/**
 * Lista infinita sobre o MESMO `CrudService.list` das listas paginadas.
 *
 * A query key mantém o prefixo `[endpoint, "list"]` de propósito: é ele que as
 * mutations do `useCrud` invalidam por prefixo. O discriminador "infinite" vai na
 * posição 2, DEPOIS de "list" — movê-lo pra posição 1 desliga silenciosamente o
 * refresh pós create/update/delete.
 */
export function useInfiniteList<T = unknown>(
  endpoint: string,
  params?: InfiniteListParams,
  options?: { enabled?: boolean; pageSize?: number }
) {
  const { createCrudService } = useDataProvider();
  // Estável por endpoint — sem isto a queryFn captura uma instância nova a cada render.
  const service = useMemo(() => createCrudService<T>(endpoint), [createCrudService, endpoint]);
  const pageSize = options?.pageSize ?? LIST_PAGE_SIZE;

  const query = useInfiniteQuery({
    queryKey: [endpoint, "list", "infinite", { ...params, limit: pageSize }],
    queryFn: ({ pageParam }) => service.list({ ...params, skip: pageParam, limit: pageSize }),
    initialPageParam: 0,
    getNextPageParam: (lastPage: PagedResponse<T>) => {
      // `skip` ecoado pelo servidor, não acumulado no cliente: se o backend
      // devolver menos que `limit`, a aritmética não desanda.
      const nextSkip = lastPage.skip + lastPage.items.length;
      // `hasMore` é exato (sentinela LIMIT+1 no backend). O fallback cobre
      // endpoint ainda não migrado, que só devolve `total`.
      const more = lastPage.hasMore ?? nextSkip < lastPage.total;
      return more ? nextSkip : undefined;
    },
    enabled: options?.enabled ?? true,
    // Divergência deliberada do `staleTime: 0` do `useList`. O frescor pós-mutation
    // vem da INVALIDAÇÃO, que ignora staleTime. Com 0 + refetchOnMount:"always", a
    // navegação lista → detalhe → voltar refaz TODAS as páginas carregadas em
    // sequência. NÃO "consertar" pra 0.
    staleTime: 30_000,
    // SEM placeholderData: keepPreviousData. Em infinite query isso segura as N
    // páginas do filtro anterior enquanto a nova página 1 carrega, e depois dá um
    // snap. O DataList escurece as linhas em vez disso.
  });

  const items = useMemo(() => query.data?.pages.flatMap((page) => page.items) ?? [], [query.data]);
  // Só a página 0 carrega o total exato — contrato do envelope (o backend só roda
  // o COUNT quando skip === 0).
  const total = query.data?.pages[0]?.total ?? 0;

  return { ...query, items, total };
}

/**
 * Sentinela de scroll infinito. Devolve um **callback ref**.
 *
 * Ref-espelho do estado é obrigatório: `observe()` dispara o callback com o alvo
 * AINDA visível, então qualquer valor que muda por render viraria dep, recriaria
 * o observer e re-dispararia. Passar o objeto `query` como dep é o erro clássico
 * — ele é uma referência nova a cada render.
 *
 * O NÓ, porém, precisa ser dep: a lista nasce em `isLoading` (sem sentinela no
 * DOM) e só monta o nó quando a primeira página chega. Com `useRef` + deps
 * vazias o efeito já teria rodado com `null` e nunca mais — o observer nunca
 * observaria nada e o scroll infinito viraria só o botão "Carregar mais".
 */
export function useInfiniteScrollSentinel({
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
}: {
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
}) {
  const [node, setNode] = useState<HTMLDivElement | null>(null);
  const state = useRef({ hasNextPage, isFetchingNextPage, fetchNextPage });
  state.current = { hasNextPage, isFetchingNextPage, fetchNextPage };

  useEffect(() => {
    if (!node || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting) return;
        const current = state.current;
        // Guarda redundante com o dedupe do TanStack, de propósito: dois callbacks
        // no mesmo tick veriam o mesmo `isFetchingNextPage` pré-commit.
        if (!current.hasNextPage || current.isFetchingNextPage) return;
        current.fetchNextPage();
      },
      { rootMargin: SENTINEL_ROOT_MARGIN }
    );
    observer.observe(node);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ver ref-espelho acima
  }, [node]);

  return setNode;
}
