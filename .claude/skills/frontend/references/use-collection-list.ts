import { useInfiniteList } from "@/hooks/useInfiniteList";
import { LIST_PAGE_SIZE, usePagedList, type PagedListParams } from "@/hooks/usePagedList";
import { useCallback, useState } from "react";

/**
 * Como uma tela de coleção percorre a lista. Os dois modos leem o MESMO endpoint
 * `PagedResponse` (total exato em toda página — `repositories/shared/listing.py`) e os dois
 * mostram "carregados de total"; muda só a navegação:
 *   pages    → números de página, `page` na URL (link para a página 7 abre a página 7).
 *   infinite → páginas anexadas ao rolar, sentinela + "Carregar mais".
 * Decisão do usuário (2026-10-09): o modo é escolha POR TELA — default no código, e quem usa
 * pode trocar no ⋮ da toolbar (`useListPreferences` + `ListOptionsMenu`). Antes era um modo por app (kailos = páginas, resto = infinito).
 */
export type ListMode = "pages" | "infinite";

/** O que o `DataList` precisa para desenhar o rodapé do modo infinito. */
export interface InfiniteListControls {
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => unknown;
}

/**
 * Lista de coleção nos dois modos, com o shape que o `DataList` espalha (`{...list}`).
 *
 * Os dois hooks são chamados sempre (regra dos hooks) e só o do modo ativo fica `enabled`.
 * No infinito, `page`/`pageCount` ficam fixos em 1 e `infinite` carrega os controles — é a
 * presença dele que põe o `DataList` no modo infinito.
 */
export function useCollectionList<T = unknown>(
  endpoint: string,
  params: PagedListParams | undefined,
  options: { mode: ListMode; page: number; pageSize?: number }
) {
  const pageSize = options.pageSize ?? LIST_PAGE_SIZE;
  const isInfinite = options.mode === "infinite";
  const paged = usePagedList<T>(endpoint, params, {
    page: options.page,
    pageSize,
    enabled: !isInfinite,
  });
  const infinite = useInfiniteList<T>(endpoint, params, { pageSize, enabled: isInfinite });

  if (!isInfinite) return { ...paged, infinite: undefined };

  return {
    items: infinite.items,
    total: infinite.total,
    isLoading: infinite.isLoading,
    // Buscar a PRÓXIMA página não é "a lista está mudando": sem tirar o `isFetchingNextPage`
    // daqui, o `DataList` escureceria tudo o que já foi carregado a cada degrau.
    isFetching: infinite.isFetching && !infinite.isFetchingNextPage,
    isError: infinite.isError,
    error: infinite.error,
    refetch: infinite.refetch,
    page: 1,
    pageSize,
    pageCount: 1,
    infinite: {
      hasNextPage: infinite.hasNextPage,
      isFetchingNextPage: infinite.isFetchingNextPage,
      fetchNextPage: infinite.fetchNextPage,
    } satisfies InfiniteListControls,
  };
}

const LIST_PREFERENCES_STORAGE_PREFIX = "list-preferences:";

/** Preferências de exibição de UMA tela de lista — o que o menu ⋮ da toolbar troca. */
export interface ListPreferences {
  mode: ListMode;
  showRecents: boolean;
}

function readStoredPreferences(screenKey: string): Partial<ListPreferences> {
  try {
    const parsed: unknown = JSON.parse(
      localStorage.getItem(LIST_PREFERENCES_STORAGE_PREFIX + screenKey) ?? "{}"
    );
    if (typeof parsed !== "object" || parsed === null) return {};
    const { mode, showRecents } = parsed as Record<string, unknown>;
    return {
      mode: mode === "pages" || mode === "infinite" ? mode : undefined,
      showRecents: typeof showRecents === "boolean" ? showRecents : undefined,
    };
  } catch {
    return {};
  }
}

/**
 * Preferências da tela: os defaults vêm do código (cada tela escolhe o seu modo), a troca do
 * usuário fica no navegador dele, por tela. Preferência de exibição, não dado — se o storage
 * falhar (aba privada), a tela segue nos defaults.
 */
export function useListPreferences(screenKey: string, defaults: ListPreferences) {
  const [preferences, setPreferences] = useState<ListPreferences>(() => {
    const stored = readStoredPreferences(screenKey);
    return {
      mode: stored.mode ?? defaults.mode,
      showRecents: stored.showRecents ?? defaults.showRecents,
    };
  });

  const updatePreferences = useCallback(
    (patch: Partial<ListPreferences>) => {
      setPreferences((current) => {
        const next = { ...current, ...patch };
        try {
          localStorage.setItem(LIST_PREFERENCES_STORAGE_PREFIX + screenKey, JSON.stringify(next));
        } catch {
          // Storage indisponível: a troca vale só nesta visita.
        }
        return next;
      });
    },
    [screenKey]
  );

  return [preferences, updatePreferences] as const;
}
