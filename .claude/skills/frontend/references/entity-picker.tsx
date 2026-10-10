import { Button } from "@/components/ui/button";
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { FIELD_TRIGGER_CLASS } from "@/components/ui/input";
import { formatCount } from "@/components/ui/list-pagination";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useInfiniteScrollSentinel } from "@/hooks/useInfiniteList";
import { cn } from "@/lib/utils";
import { useRef, useState, type ReactNode } from "react";
import { LuChevronsUpDown, LuPlus, LuX } from "react-icons/lu";

/**
 * O que o `useList` de um picker devolve — o shape do `useInfiniteList`/`useInfinitePages`
 * (`hooks/useInfiniteList.ts`), então `useList={(p, o) => useInfiniteList(endpoint, p, o)}`
 * encaixa direto. Páginas ANEXADAS, nunca um `limit` crescente na query key: ver o porquê
 * em `useInfinitePages`.
 */
export interface EntityPickerSource<T> {
  items: T[];
  total: number;
  hasNextPage: boolean;
  isFetching: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => unknown;
}

interface EntityPickerProps<T> {
  /** Hook de lista do caller — chamado incondicionalmente, `enabled` só com o popover aberto. */
  useList: (params: { search?: string }, options: { enabled: boolean }) => EntityPickerSource<T>;
  value: string | null;
  /** Label já conhecido (edição) — evita "carregando" antes da lista chegar. */
  valueLabel?: string | null;
  onChange: (id: string | null, label: string | null, item: T | null) => void;
  getId: (item: T) => string;
  getLabel: (item: T) => string;
  renderItem?: (item: T) => ReactNode;
  placeholder: string;
  searchPlaceholder: string;
  emptyText: string;
  /** Quick-create: omitir os dois juntos desliga o CTA "Novo…". */
  createLabel?: string;
  onCreateNew?: () => void;
  clearable?: boolean;
  disabled?: boolean;
  /** Valor em fonte mono (placas, códigos). */
  monoValue?: boolean;
}

/**
 * Busca no servidor (`search`), sem filtro client-side — a lista é sempre um recorte.
 * Rolar até o fim anexa a próxima página (sentinela), sem teto: quem tem 2.000 contatos
 * rola até o 2.000º se quiser.
 *
 * Rodapé FIXO fora da área de rolagem: "10 de 1.355" + o CTA "Novo…", a faixa inteira
 * clicável. O CTA ficava no fim
 * da lista rolável — com scroll infinito ele só aparecia depois de rolar tudo (pedido do
 * usuário, 2026-10-09: criar novo sempre à vista, estilo admin do Django).
 */
export function EntityPicker<T>({
  useList,
  value,
  valueLabel,
  onChange,
  getId,
  getLabel,
  renderItem,
  placeholder,
  searchPlaceholder,
  emptyText,
  createLabel,
  onCreateNew,
  clearable = true,
  disabled = false,
  monoValue = false,
}: EntityPickerProps<T>) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  // Guarda o foco de retorno do Popover quando "Novo…" abre um Dialog: sem isso o
  // focus-restore do Popover briga com o onOpenAutoFocus do Dialog aninhado.
  const creatingRef = useRef(false);
  const list = useList({ search: query || undefined }, { enabled: open });
  const sentinelRef = useInfiniteScrollSentinel({
    hasNextPage: list.hasNextPage,
    isFetchingNextPage: list.isFetchingNextPage,
    fetchNextPage: list.fetchNextPage,
  });

  const { items, total } = list;
  const selected = value ? items.find((item) => getId(item) === value) : undefined;
  const selectedLabel = value ? (selected ? getLabel(selected) : (valueLabel ?? null)) : null;
  const canCreate = Boolean(createLabel && onCreateNew);

  const startCreate = () => {
    creatingRef.current = true;
    setOpen(false);
    onCreateNew?.();
  };

  return (
    <div className="flex items-center gap-2">
      {/* `modal`: dentro de um Dialog o Radix trava o scroll (react-remove-scroll) e o
          conteúdo portalado ficava FORA da trava — a roda do mouse não rolava a lista, só a
          barra arrastada. Modal, o Popover empilha a própria trava (a última vence) e libera
          o próprio conteúdo. Substitui o listener de `wheel`/`touchmove` reinjetado à mão. */}
      <Popover open={open} onOpenChange={setOpen} modal>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={disabled}
            // Campo de formulário segue a métrica de Input, não a escala de botão do projeto.
            className={cn(FIELD_TRIGGER_CLASS, "flex flex-1 justify-between font-normal")}
          >
            <span
              className={cn(
                "truncate",
                !selectedLabel && "text-muted-foreground",
                monoValue && selectedLabel && "font-mono"
              )}
            >
              {selectedLabel ?? placeholder}
            </span>
            <LuChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className="w-(--radix-popover-trigger-width) p-0"
          align="start"
          onCloseAutoFocus={(event) => {
            if (creatingRef.current) {
              event.preventDefault();
              creatingRef.current = false;
            }
          }}
        >
          <Command shouldFilter={false}>
            <CommandInput placeholder={searchPlaceholder} value={query} onValueChange={setQuery} />
            <CommandList>
              {/* shouldFilter=false: o vazio é decidido pelo servidor (items.length),
                  nunca pelo auto-hide do CommandEmpty. */}
              {items.length === 0 && (
                <p className="text-muted-foreground py-6 text-center text-sm">
                  {list.isFetching ? "Carregando…" : emptyText}
                </p>
              )}
              {items.length > 0 && (
                <CommandGroup>
                  {items.map((item) => (
                    <CommandItem
                      key={getId(item)}
                      value={getId(item)}
                      onSelect={() => {
                        onChange(getId(item), getLabel(item), item);
                        setOpen(false);
                      }}
                    >
                      {/* Wrapper `flex-1`: o `CommandItem` já termina num ícone de check com
                          `ml-auto`; um `ml-auto` do `renderItem` (telefone, placa) dividia a
                          sobra com ele e a 2ª coluna saía torta, cada linha numa posição. */}
                      <span className="flex min-w-0 flex-1 items-center gap-2">
                        {renderItem ? (
                          renderItem(item)
                        ) : (
                          <span className="truncate">{getLabel(item)}</span>
                        )}
                      </span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
              {list.hasNextPage && (
                // Clicável: lista que não enche a altura não gera rolagem, e a sentinela só
                // carrega com rolagem de verdade (`useInfiniteScrollSentinel`).
                <div ref={sentinelRef} className="flex justify-center py-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground text-xs"
                    disabled={list.isFetchingNextPage}
                    onClick={() => list.fetchNextPage()}
                  >
                    {list.isFetchingNextPage ? "Carregando…" : "Carregar mais"}
                  </Button>
                </div>
              )}
            </CommandList>
            {canCreate ? (
              // A faixa INTEIRA é o botão (contagem incluída): alvo grande, sempre à vista.
              // "Novo…" à esquerda, alinhado ao texto dos itens como mais uma opção da lista;
              // no canto direito ele ficava solto, longe de tudo (feedback 2026-10-09).
              <button
                type="button"
                onClick={startCreate}
                className="hover:bg-muted focus-visible:bg-muted mt-1 flex w-full items-center gap-2 rounded-md border-t px-2.5 py-2 text-left text-xs outline-hidden"
              >
                <LuPlus className="size-3.5 shrink-0" />
                <span className="font-medium">{createLabel}</span>
                {total > 0 && (
                  <span className="ml-auto">
                    <FooterCount loaded={items.length} total={total} />
                  </span>
                )}
              </button>
            ) : (
              total > 0 && (
                <div className="mt-1 border-t px-2.5 py-2 text-xs">
                  <FooterCount loaded={items.length} total={total} />
                </div>
              )
            )}
          </Command>
        </PopoverContent>
      </Popover>

      {clearable && value && !disabled && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Limpar seleção"
          onClick={() => onChange(null, null, null)}
        >
          <LuX className="size-4" />
        </Button>
      )}
    </div>
  );
}

function FooterCount({ loaded, total }: { loaded: number; total: number }) {
  return (
    <span className="text-muted-foreground tabular-nums">
      {formatCount(loaded)} de {formatCount(total)}
    </span>
  );
}
