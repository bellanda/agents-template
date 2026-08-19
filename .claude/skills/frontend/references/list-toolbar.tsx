import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormDialog } from "@/components/ui/form-dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { LuListFilter, LuSearch, LuX } from "react-icons/lu";

/** Espelha `MIN_SEARCH_LENGTH` do backend — abaixo disso não há busca nenhuma. */
export const MIN_SEARCH_LENGTH = 3;
/** Janela do debounce. Cada tecla commitada na URL = uma entrada de histórico. */
const SEARCH_DEBOUNCE_MS = 300;

export type SortOrder = "asc" | "desc";

export interface SortOption {
  /** Valor do Select — `"{sort}:{order}"`. */
  value: string;
  label: string;
  sort: string;
  order: SortOrder;
}

/**
 * As 5 opções canônicas cross-projeto. São apresentadas como opções concretas e
 * rotuladas, NÃO como chave + toggle de direção: uma combinação ilegal a menos e
 * um controle a menos no celular.
 *
 * `alphaKey` é a coluna alfabética da entidade e precisa ser `NOT NULL` (regra do
 * whitelist do backend) — `name` em clientes, `plate` em veículos, `number` em OS.
 * Entidade SEM coluna alfabética `NOT NULL` (manutenção, contagem de inventário —
 * identificadas por quando aconteceram) chama `makeSortOptions()` sem argumento e
 * fica só com as opções de data; inventar uma chave nullable aqui quebraria o
 * whitelist do backend e cairia calado no default.
 */
export function makeSortOptions(alpha?: { alphaKey: string; alphaLabel: string }): SortOption[] {
  return [
    { value: "created_at:desc", label: "Mais recentes", sort: "created_at", order: "desc" },
    { value: "created_at:asc", label: "Mais antigos", sort: "created_at", order: "asc" },
    ...(alpha
      ? ([
          {
            value: `${alpha.alphaKey}:asc`,
            label: `${alpha.alphaLabel} (A → Z)`,
            sort: alpha.alphaKey,
            order: "asc",
          },
          {
            value: `${alpha.alphaKey}:desc`,
            label: `${alpha.alphaLabel} (Z → A)`,
            sort: alpha.alphaKey,
            order: "desc",
          },
        ] satisfies SortOption[])
      : []),
    {
      value: "updated_at:desc",
      label: "Atualizados por último",
      sort: "updated_at",
      order: "desc",
    },
  ];
}

/**
 * Campo de busca com debounce.
 *
 * O texto em digitação é o ÚNICO `useState` legítimo de uma tela de lista — é
 * buffer transitório de teclas, não estado de filtro. O filtro commitado mora na
 * URL.
 */
export function SearchInput({
  value,
  onCommit,
  placeholder,
  minLength = MIN_SEARCH_LENGTH,
  delay = SEARCH_DEBOUNCE_MS,
  className,
}: {
  value: string | undefined;
  /** DEVE ser estável (`useCallback`) — entra nas deps do debounce. */
  onCommit: (next: string | undefined) => void;
  placeholder: string;
  minLength?: number;
  delay?: number;
  className?: string;
}) {
  const [draft, setDraft] = useState(value ?? "");
  // Última string que ESTE input mandou pra URL. Se `value` divergir dela, a
  // mudança veio de fora (voltar do browser, "limpar filtros") → ressincroniza.
  // `key={value}` no Input resolveria também, mas remonta e perde o foco digitando.
  const committed = useRef(value ?? "");

  useEffect(() => {
    const next = value ?? "";
    if (next !== committed.current) {
      committed.current = next;
      setDraft(next);
    }
  }, [value]);

  useEffect(() => {
    const term = draft.trim();
    const next = term.length >= minLength ? term : "";
    if (next === committed.current) return;
    const timer = setTimeout(() => {
      committed.current = next;
      onCommit(next || undefined);
    }, delay);
    return () => clearTimeout(timer);
  }, [draft, minLength, delay, onCommit]);

  return (
    <div className={cn("relative w-full sm:max-w-sm", className)}>
      <LuSearch className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2" />
      <Input
        className="pl-9"
        type="search"
        placeholder={placeholder}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
      />
      {draft && (
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Limpar busca"
          className="absolute top-1/2 right-1 -translate-y-1/2"
          onClick={() => setDraft("")}
        >
          <LuX className="size-4" />
        </Button>
      )}
    </div>
  );
}

function SortSelect({
  sort,
  order,
  options,
  onChange,
  className,
}: {
  sort: string | undefined;
  order: SortOrder | undefined;
  options: SortOption[];
  onChange: (sort: string, order: SortOrder) => void;
  className?: string;
}) {
  const current = options.find((o) => o.sort === sort && o.order === order) ?? options[0];
  return (
    <Select
      value={current?.value}
      onValueChange={(next) => {
        const option = options.find((o) => o.value === next);
        if (option) onChange(option.sort, option.order);
      }}
    >
      <SelectTrigger className={cn("w-full sm:w-56", className)} aria-label="Ordenar por">
        <SelectValue placeholder="Ordenar por" />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export interface ListToolbarProps {
  search?: string;
  /**
   * DEVE ser estável (`useCallback`). Omitir esconde o campo de busca — é o caso
   * da coleção sem `search` no backend (sessões de inventário, logs de execução),
   * onde um input que não filtra nada é pior que input nenhum.
   */
  onSearchChange?: (next: string | undefined) => void;
  searchPlaceholder?: string;

  sort?: string;
  order?: SortOrder;
  sortOptions?: SortOption[];
  onSortChange?: (sort: string, order: SortOrder) => void;

  /** Selects/toggles de filtro da entidade. No mobile vão pro dialog "Filtros". */
  filters?: ReactNode;
  /** Quantos filtros estão ativos — alimenta o badge do botão no mobile. */
  activeFilterCount?: number;
  onClearFilters?: () => void;

  /** Botão de criar e afins. SEMPRE aqui, nunca abaixo da lista (scroll infinito). */
  actions?: ReactNode;
  className?: string;
}

/**
 * Toolbar canônica de tela de lista: busca + filtros + ordenação + ações.
 *
 * Presentational — recebe valores e callbacks; quem chama `navigate()` é a tela
 * (o `search` tipado do TanStack Router é por rota, não daria pra vendorar
 * genericamente nos 5 projetos).
 *
 * Fica ACIMA da lista. Numa rota de lista nada pode ficar abaixo dela: com
 * scroll infinito, o fim da página nunca chega.
 */
export function ListToolbar({
  search,
  onSearchChange,
  searchPlaceholder,
  sort,
  order,
  sortOptions,
  onSortChange,
  filters,
  activeFilterCount = 0,
  onClearFilters,
  actions,
  className,
}: ListToolbarProps) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const hasSort = Boolean(sortOptions?.length && onSortChange);
  const hasCollapsible = Boolean(filters) || hasSort;

  const closeFilters = useCallback(() => setFiltersOpen(false), []);

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {onSearchChange ? (
          <SearchInput
            value={search}
            onCommit={onSearchChange}
            placeholder={searchPlaceholder ?? "Buscar…"}
            className="flex-1"
          />
        ) : (
          // Sem busca as ações continuam à direita em vez de colarem na esquerda.
          <div className="hidden flex-1 sm:block" />
        )}

        <div className="flex items-center gap-2">
          {hasCollapsible && (
            <Button
              variant="outline"
              className="md:hidden"
              onClick={() => setFiltersOpen(true)}
              aria-label="Filtros e ordenação"
            >
              <LuListFilter className="mr-2 size-4" />
              Filtros
              {activeFilterCount > 0 && (
                <Badge variant="secondary" className="ml-2">
                  {activeFilterCount}
                </Badge>
              )}
            </Button>
          )}
          {actions}
        </div>
      </div>

      {/* Desktop: filtros e ordenação inline. Mobile: dentro do dialog. */}
      {hasCollapsible && (
        <div className="hidden flex-wrap items-center gap-2 md:flex">
          {filters}
          {hasSort && (
            <SortSelect
              sort={sort}
              order={order}
              options={sortOptions!}
              onChange={onSortChange!}
              className="ml-auto"
            />
          )}
          {activeFilterCount > 0 && onClearFilters && (
            <Button variant="ghost" size="sm" onClick={onClearFilters}>
              Limpar filtros
            </Button>
          )}
        </div>
      )}

      {hasCollapsible && (
        // Dialog, não Sheet nem Drawer: `overlays.md` proíbe Sheet lateral no app
        // e `vaul` não é dependência de nenhum dos 5.
        <FormDialog
          open={filtersOpen}
          onOpenChange={setFiltersOpen}
          title="Filtros e ordenação"
          size="sm"
          bodyClassName="space-y-4"
          footer={
            <>
              {activeFilterCount > 0 && onClearFilters && (
                <Button
                  variant="outline"
                  onClick={() => {
                    onClearFilters();
                    closeFilters();
                  }}
                >
                  Limpar
                </Button>
              )}
              <Button onClick={closeFilters}>Aplicar</Button>
            </>
          }
        >
          {filters}
          {hasSort && (
            <SortSelect
              sort={sort}
              order={order}
              options={sortOptions!}
              onChange={onSortChange!}
              className="w-full"
            />
          )}
        </FormDialog>
      )}
    </div>
  );
}
