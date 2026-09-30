import { useCallback, useMemo, useRef, useState } from "react";

/**
 * Seleção múltipla de uma lista — paginada por número (`pageItems` = a página) ou
 * scroll infinito (`pageItems` = os itens carregados).
 *
 * O estado mora na TELA, não no `DataList` — mesmo princípio do `ListToolbar`:
 * quem seleciona é quem age sobre a seleção, e a lista só desenha o checkbox.
 *
 * **A seleção atravessa páginas.** Guarda o ITEM, não só o id: marcar 5 na página 1
 * e 3 na página 2 publica os 8, e a ação em lote precisa do rótulo de quem já saiu
 * da tela. "Selecionar todos" vale para a página visível — o rótulo no
 * `BulkActionsMenu` diz isso.
 *
 * Limpar é responsabilidade do call site, chamado DENTRO dos próprios handlers de
 * busca/filtro. Um `useEffect` observando os filtros faria a limpeza acontecer um
 * render DEPOIS, e nesse intervalo a barra ofereceria ação sobre item que já
 * saiu do filtro.
 */
export function useListSelection<T>(pageItems: T[], getId: (item: T) => string) {
  const [selected, setSelected] = useState<ReadonlyMap<string, T>>(() => new Map<string, T>());

  // Ref-espelho: `pageItems` e `getId` mudam de identidade a cada render da tela, e
  // como dependência recriariam os callbacks em todo render.
  const pageRef = useRef({ pageItems, getId });
  pageRef.current = { pageItems, getId };

  const toggle = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.delete(id)) return next;
      const { pageItems: items, getId: idOf } = pageRef.current;
      const item = items.find((candidate) => idOf(candidate) === id);
      if (item !== undefined) next.set(id, item);
      return next;
    });
  }, []);

  const clear = useCallback(() => setSelected(new Map<string, T>()), []);

  const togglePage = useCallback(() => {
    setSelected((prev) => {
      const { pageItems: items, getId: idOf } = pageRef.current;
      const allSelected = items.length > 0 && items.every((item) => prev.has(idOf(item)));
      const next = new Map(prev);
      for (const item of items) {
        if (allSelected) next.delete(idOf(item));
        else next.set(idOf(item), item);
      }
      return next;
    });
  }, []);

  const pageIds = pageItems.map(getId);
  const allOnPageSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const selectedIds = useMemo<ReadonlySet<string>>(() => new Set(selected.keys()), [selected]);
  // Ordem de clique entre páginas; é a ordem em que a ação em lote vai processar.
  const selectedItems = useMemo(() => [...selected.values()], [selected]);

  return {
    selectedIds,
    selectedItems,
    count: selected.size,
    allOnPageSelected,
    toggle,
    togglePage,
    clear,
  };
}
