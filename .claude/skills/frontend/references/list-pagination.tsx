import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { LuChevronLeft, LuChevronRight } from "react-icons/lu";

/** Vizinhos da página atual que aparecem numerados, além da primeira e da última. */
const SIBLING_PAGES = 1;

type PageSlot = number | "gap-before" | "gap-after";

const countFormatter = new Intl.NumberFormat("pt-BR");

/** "1.355" — total e faixa com separador de milhar. */
export function formatCount(value: number): string {
  return countFormatter.format(value);
}

/**
 * `1 … 4 5 6 … 68`: primeira, última, a atual e os vizinhos. Um buraco de uma
 * página só vira o número (reticências no lugar de "2" esconderia um clique).
 */
export function pageSlots(page: number, pageCount: number): PageSlot[] {
  const pages = new Set<number>([1, pageCount]);
  for (let candidate = page - SIBLING_PAGES; candidate <= page + SIBLING_PAGES; candidate++) {
    if (candidate >= 1 && candidate <= pageCount) pages.add(candidate);
  }
  const sorted = [...pages].sort((a, b) => a - b);
  const slots: PageSlot[] = [];
  sorted.forEach((current, index) => {
    const previous = sorted[index - 1];
    if (previous !== undefined && current - previous === 2) slots.push(previous + 1);
    if (previous !== undefined && current - previous > 2) {
      slots.push(current <= page ? "gap-before" : "gap-after");
    }
    slots.push(current);
  });
  return slots;
}

interface ListPaginationProps {
  page: number;
  pageCount: number;
  pageSize: number;
  total: number;
  /** "1.355 veículos" — sem ele, só o número. */
  countLabel?: (total: number) => string;
  onPageChange: (page: number) => void;
  /**
   * Esconde "21–40 de 1.355" aqui embaixo — o `DataList` já mostra o resumo no TOPO da lista
   * (decisão de 2026-10-09) e a mesma faixa duas vezes na tela só polui.
   */
  hideRange?: boolean;
  className?: string;
}

/**
 * Rodapé de lista paginada: faixa + total à esquerda, páginas à direita.
 *
 * No celular os números saem e fica "‹ Página 2 de 68 ›" com alvos de 44px —
 * sete botões de 36px não cabem em 375px sem quebrar linha.
 */
export function ListPagination({
  page,
  pageCount,
  pageSize,
  total,
  countLabel,
  onPageChange,
  hideRange = false,
  className,
}: ListPaginationProps) {
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  const totalLabel = countLabel ? countLabel(total) : formatCount(total);
  const range = from === to ? formatCount(from) : `${formatCount(from)}–${formatCount(to)}`;

  return (
    <nav
      aria-label="Paginação"
      className={cn("flex flex-col items-center gap-3 sm:flex-row sm:justify-between", className)}
    >
      {!hideRange && (
        <p aria-live="polite" className="text-muted-foreground text-sm tabular-nums">
          {range} de {totalLabel}
        </p>
      )}

      {pageCount > 1 && (
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            className="max-sm:size-11"
            aria-label="Página anterior"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            <LuChevronLeft />
          </Button>

          <span className="px-3 text-sm tabular-nums sm:hidden">
            Página {page} de {pageCount}
          </span>

          <div className="hidden items-center gap-1 sm:flex">
            {pageSlots(page, pageCount).map((slot) =>
              typeof slot === "number" ? (
                <Button
                  key={slot}
                  variant={slot === page ? "default" : "ghost"}
                  size="icon"
                  className="w-auto min-w-9 px-2 tabular-nums"
                  aria-label={`Página ${slot}`}
                  aria-current={slot === page ? "page" : undefined}
                  onClick={() => onPageChange(slot)}
                >
                  {slot}
                </Button>
              ) : (
                <span key={slot} aria-hidden className="text-muted-foreground w-6 text-center">
                  …
                </span>
              )
            )}
          </div>

          <Button
            variant="outline"
            size="icon"
            className="max-sm:size-11"
            aria-label="Próxima página"
            disabled={page >= pageCount}
            onClick={() => onPageChange(page + 1)}
          >
            <LuChevronRight />
          </Button>
        </div>
      )}
    </nav>
  );
}
