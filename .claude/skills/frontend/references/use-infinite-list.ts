import { useDataProvider } from "@/lib/api/context";
import type { ListRequest, PagedResponse } from "@/lib/api/types";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

/** 10 por vez: com ORDER BY indexado e sentinela LIMIT+1, cada degrau é barato. */
export const LIST_PAGE_SIZE = 10;

/**
 * Folga para considerar "chegou ao fim": a sentinela a até ~meia linha abaixo da borda
 * visível já conta. Não é pré-busca — é tolerância de arredondamento/padding.
 */
const END_REACHED_TOLERANCE_PX = 24;

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

  return useInfinitePages<T>({
    queryKey: [endpoint, "list", "infinite", { ...params, limit: pageSize }],
    fetchPage: ({ skip, limit }) => service.list({ ...params, skip, limit }),
    enabled: options?.enabled,
    pageSize,
  });
}

export interface InfinitePagesOptions<T> {
  /** Sem `skip`/`limit` — a página é o `pageParam`, não parte da chave. */
  queryKey: readonly unknown[];
  fetchPage: (page: { skip: number; limit: number }) => Promise<PagedResponse<T>>;
  enabled?: boolean;
  pageSize?: number;
}

/**
 * Motor de páginas acumuladas para QUALQUER endpoint `PagedResponse` — o `useInfiniteList`
 * (CrudService) e os adapters de `EntityPicker` cujo endpoint não cabe no CrudService
 * (`/contacts?org_id=`, rota de plataforma) passam todos por aqui.
 *
 * Página nova é ANEXADA às anteriores. Era o que faltava no picker antigo, que crescia o
 * `limit` (10 → 20 → 30…) com o `limit` na query key: cada degrau era uma chave nova sem
 * dado, a lista colapsava em "Carregando…", o scroll voltava a 0 e a lista nunca passava
 * do começo (bug relatado em 2026-10-09 no picker de Contato da Ficha). De quebra cada
 * degrau rebaixava as linhas já vistas e havia um teto de 200.
 */
export function useInfinitePages<T>({
  queryKey,
  fetchPage,
  enabled = true,
  pageSize = LIST_PAGE_SIZE,
}: InfinitePagesOptions<T>) {
  const query = useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam }) => fetchPage({ skip: pageParam, limit: pageSize }),
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
    enabled,
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
  // Lido da página 0: é nela que o `removeRowFromListCaches` do `useCrud` desconta a
  // linha excluída, então é ela que fica certa depois de um splice local.
  const total = query.data?.pages[0]?.total ?? 0;

  return { ...query, items, total };
}

/**
 * Sentinela de scroll infinito. Devolve um **callback ref** para o elemento no fim da lista.
 *
 * Carrega a próxima página SÓ quando o usuário ROLA e o fim do que já está carregado entra
 * na tela (pedido do usuário, 2026-10-09: "carrega somente depois de rolar até o final da
 * lista carregada atual, não fica carregando sozinho"). Nada de pré-busca nem de reavaliar
 * sozinho depois que uma página chega — a versão com IntersectionObserver fazia as duas e
 * encadeava páginas sem ninguém rolar ("rolando sem rolar"): o `root` era achado pelo
 * `overflow-y` computado, e um ancestral com `overflow-x-hidden` vira `overflow-y: auto` sem
 * rolar nada — sentinela "sempre visível", lista inteira carregada.
 *
 * Como: um listener de `scroll` em CAPTURA no `document` pega a rolagem de qualquer
 * contêiner (o `<main>` do `SidebarLayout`, a lista do picker, a janela na vitrine) sem
 * precisar descobrir qual é. Lista que não enche a tela não gera rolagem — aí vale o botão
 * "Carregar mais" que toda lista infinita mostra junto da sentinela.
 *
 * Ref-espelho do estado: o listener lê `hasNextPage`/`fetchNextPage` do espelho, nunca de
 * dep — passar o objeto `query` como dep é o erro clássico (referência nova a cada render).
 * O NÓ é dep: a lista nasce em `isLoading` e só monta a sentinela quando a 1ª página chega.
 */
export function useInfiniteScrollSentinel({
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
}: {
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => unknown;
}) {
  const [node, setNode] = useState<HTMLDivElement | null>(null);
  const state = useRef({ hasNextPage, isFetchingNextPage, fetchNextPage });
  state.current = { hasNextPage, isFetchingNextPage, fetchNextPage };

  useEffect(() => {
    if (!node) return;

    const loadIfReachedEnd = (event: Event) => {
      const current = state.current;
      if (!current.hasNextPage || current.isFetchingNextPage) return;
      const scroller = event.target;
      // Rolagem de OUTRO contêiner (um dialog, outra lista) não é desta lista.
      if (scroller instanceof Element && !scroller.contains(node)) return;
      const visibleBottom =
        scroller instanceof Element ? scroller.getBoundingClientRect().bottom : window.innerHeight;
      if (node.getBoundingClientRect().top <= visibleBottom + END_REACHED_TOLERANCE_PX) {
        current.fetchNextPage();
      }
    };

    document.addEventListener("scroll", loadIfReachedEnd, { capture: true, passive: true });
    return () => document.removeEventListener("scroll", loadIfReachedEnd, { capture: true });
  }, [node]);

  return setNode;
}
