import { Button } from "@/components/ui/button";
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { FIELD_TRIGGER_CLASS } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { ListRequest, PagedResponse } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { useEffect, useRef, useState, type ReactNode, type UIEvent } from "react";
import { LuChevronsUpDown, LuPlus, LuX } from "react-icons/lu";

const PAGE_SIZE = 10;
/** Distância do fim da lista que dispara o próximo degrau — ~meia linha. */
const LOAD_MORE_THRESHOLD_PX = 32;

interface EntityPickerProps<T> {
  /** Hook de lista do caller (ex.: `useVehicles(orgId).useList`) — chamado incondicionalmente. */
  useList: (
    params: ListRequest,
    options: { enabled: boolean }
  ) => { data?: PagedResponse<T>; isFetching?: boolean };
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
 * Rola até o fim para subir o próprio `limit` de 10 em 10: a query key carrega o `limit`,
 * então cada degrau é uma entrada de cache e o TanStack serve o anterior enquanto busca.
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
  const [limit, setLimit] = useState(PAGE_SIZE);
  // Guarda o foco de retorno do Popover quando "Novo…" abre um Dialog: sem isso o
  // focus-restore do Popover briga com o onOpenAutoFocus do Dialog aninhado.
  const creatingRef = useRef(false);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const { data, isFetching } = useList({ search: query || undefined, limit }, { enabled: open });

  // Quando o picker abre dentro de um Dialog, o Radix trava o scroll (react-remove-scroll)
  // e o PopoverContent é portalado pra fora do lock → roda do mouse e toque são bloqueados
  // (só a barra escapa). React trata `wheel` como passivo, então reinjetamos o scroll num
  // listener nativo não-passivo na lista. No boundary deixa o chaining seguir pra página.
  useEffect(() => {
    if (!open) return;
    const list = contentRef.current?.querySelector<HTMLElement>('[data-slot="command-list"]');
    if (!list) return;

    const scrollByDelta = (deltaY: number) => {
      if (list.scrollHeight <= list.clientHeight) return false;
      const atTop = list.scrollTop <= 0;
      const atBottom = list.scrollTop + list.clientHeight >= list.scrollHeight - 1;
      if ((deltaY < 0 && atTop) || (deltaY > 0 && atBottom)) return false;
      list.scrollTop += deltaY;
      return true;
    };

    const onWheel = (event: WheelEvent) => {
      const factor = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? list.clientHeight : 1;
      if (scrollByDelta(event.deltaY * factor)) event.preventDefault();
    };

    let lastTouchY = 0;
    const onTouchStart = (event: TouchEvent) => {
      lastTouchY = event.touches[0]?.clientY ?? 0;
    };
    const onTouchMove = (event: TouchEvent) => {
      const y = event.touches[0]?.clientY ?? 0;
      const delta = lastTouchY - y;
      lastTouchY = y;
      if (scrollByDelta(delta)) event.preventDefault();
    };

    list.addEventListener("wheel", onWheel, { passive: false });
    list.addEventListener("touchstart", onTouchStart, { passive: false });
    list.addEventListener("touchmove", onTouchMove, { passive: false });
    return () => {
      list.removeEventListener("wheel", onWheel);
      list.removeEventListener("touchstart", onTouchStart);
      list.removeEventListener("touchmove", onTouchMove);
    };
  }, [open]);

  const items = data?.items ?? [];
  const hasMore = items.length < (data?.total ?? 0);
  const selected = value ? items.find((item) => getId(item) === value) : undefined;
  const selectedLabel = value ? (selected ? getLabel(selected) : (valueLabel ?? null)) : null;
  const canCreate = Boolean(createLabel && onCreateNew);

  const search = (next: string) => {
    setQuery(next);
    setLimit(PAGE_SIZE);
  };

  const toggle = (next: boolean) => {
    setOpen(next);
    if (!next) setLimit(PAGE_SIZE);
  };

  const loadMoreOnScroll = (event: UIEvent<HTMLDivElement>) => {
    if (!hasMore || isFetching) return;
    const list = event.currentTarget;
    const remaining = list.scrollHeight - list.scrollTop - list.clientHeight;
    if (remaining <= LOAD_MORE_THRESHOLD_PX) setLimit((current) => current + PAGE_SIZE);
  };

  const startCreate = () => {
    creatingRef.current = true;
    setOpen(false);
    onCreateNew?.();
  };

  return (
    <div className="flex items-center gap-2">
      <Popover open={open} onOpenChange={toggle}>
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
          ref={contentRef}
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
            <CommandInput placeholder={searchPlaceholder} value={query} onValueChange={search} />
            <CommandList onScroll={loadMoreOnScroll}>
              {/* shouldFilter=false: o vazio é decidido pelo servidor (items.length),
                  nunca pelo auto-hide do CommandEmpty — o CTA sempre-presente o mataria. */}
              {items.length === 0 && (
                <p className="text-muted-foreground py-6 text-center text-sm">
                  {isFetching ? "Carregando…" : emptyText}
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
                      {renderItem ? (
                        renderItem(item)
                      ) : (
                        <span className="truncate">{getLabel(item)}</span>
                      )}
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
              {hasMore && (
                <p className="text-muted-foreground py-2 text-center text-xs">
                  Role para carregar mais…
                </p>
              )}
              {canCreate && (
                <>
                  {items.length > 0 && <CommandSeparator />}
                  <CommandGroup>
                    <CommandItem value="__create__" onSelect={startCreate}>
                      <LuPlus className="size-4" />
                      {createLabel}
                    </CommandItem>
                  </CommandGroup>
                </>
              )}
            </CommandList>
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
