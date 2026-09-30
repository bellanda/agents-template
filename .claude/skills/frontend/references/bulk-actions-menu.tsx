import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ReactNode } from "react";
import { LuListChecks } from "react-icons/lu";

interface BulkActionsMenuProps {
  /** Quantos itens estão marcados (em todas as páginas). */
  count: number;
  /** Itens da página visível — é o alcance real do "selecionar a página". */
  pageItemCount: number;
  allOnPageSelected: boolean;
  onTogglePage: () => void;
  onClear: () => void;
  /**
   * Alcance do "selecionar" dito no item: "desta página" em lista paginada por
   * número, "carregados" em scroll infinito (`useInfiniteList`).
   */
  scopeLabel?: string;
  /**
   * As ações em lote, como `DropdownMenuItem`. Cada uma decide sozinha se está
   * habilitada (quantos dos marcados ela alcança). Ação nova = um item a mais.
   */
  children: ReactNode;
}

/**
 * Seleção múltipla como menu no slot `actions` do `ListToolbar`, ao lado de "Novo…".
 *
 * Puramente apresentacional: o estado vem do `useListSelection` da tela, e os
 * checkboxes ficam nos cards (`DataList.selection`). Substitui a barra que ficava
 * solta entre a toolbar e a lista.
 *
 * O item diz **"os N desta página"** de propósito: um "selecionar todos" que marcasse
 * só a página visível faria o usuário publicar 24 de 169 achando que publicou tudo.
 */
export function BulkActionsMenu({
  count,
  pageItemCount,
  allOnPageSelected,
  onTogglePage,
  onClear,
  scopeLabel = "desta página",
  children,
}: BulkActionsMenuProps) {
  const pageLabel = pageItemCount === 1 ? "o 1" : `os ${pageItemCount}`;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">
          <LuListChecks className="mr-2 h-4 w-4" />
          Ações
          {count > 0 && (
            <Badge variant="secondary" className="ml-2 tabular-nums">
              {count}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="text-muted-foreground font-normal">
          {count === 0
            ? "Marque nos cards ou pela página"
            : `${count} selecionado${count === 1 ? "" : "s"}`}
        </DropdownMenuLabel>
        <DropdownMenuItem disabled={pageItemCount === 0} onClick={onTogglePage}>
          {allOnPageSelected ? "Desmarcar" : "Selecionar"} {pageLabel} {scopeLabel}
        </DropdownMenuItem>
        <DropdownMenuItem disabled={count === 0} onClick={onClear}>
          Limpar seleção
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {children}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
