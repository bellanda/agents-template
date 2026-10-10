import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { formatCount } from "@/components/ui/list-pagination";
import type { InfiniteListControls, ListMode } from "@/hooks/useCollectionList";
import { useInfiniteScrollSentinel } from "@/hooks/useInfiniteList";
import type { RecentEntry } from "@/hooks/useRecentlyOpened";
import { cn } from "@/lib/utils";
import { createContext, use, type ReactNode } from "react";
import { LuEllipsisVertical, LuHistory } from "react-icons/lu";

/**
 * Peças de tela de lista que NÃO são a lista: o menu ⋮ de preferências (vai na toolbar), o
 * resumo de totais (topo da lista), o carregador do modo infinito (fim da lista) e a faixa
 * de abertos recentemente (entre a toolbar e a lista). Decisões do usuário, 2026-10-09:
 * configuração no ⋮ do topo, totais no topo, atalho visível para o que acabou de abrir.
 */

/** Ação secundária da toolbar que, abaixo de 768px, mora no ⋮ em vez de ocupar a linha. */
export interface ToolbarMenuAction {
  label: string;
  icon?: ReactNode;
  onSelect: () => void;
  disabled?: boolean;
}

/**
 * Ponte `ListToolbar` → `ListOptionsMenu`: a toolbar publica as ações secundárias do celular
 * e o ⋮ (que o call site monta no slot `menu`) as lista acima das opções de exibição. Contexto
 * em vez de prop porque o `ListOptionsMenu` é criado pela tela, não pela toolbar. Os itens
 * levam `md:hidden`: no desktop as mesmas ações continuam na linha, o ⋮ fica só com exibição.
 */
export const ToolbarMenuActionsContext = createContext<readonly ToolbarMenuAction[]>([]);

function ToolbarMenuActionItems() {
  const actions = use(ToolbarMenuActionsContext);
  if (actions.length === 0) return null;
  return (
    <>
      {actions.map((action) => (
        <DropdownMenuItem
          key={action.label}
          className="md:hidden"
          disabled={action.disabled}
          onSelect={action.onSelect}
        >
          {action.icon}
          {action.label}
        </DropdownMenuItem>
      ))}
      <DropdownMenuSeparator className="md:hidden" />
    </>
  );
}

/** ⋮ só do celular, para tela SEM `ListOptionsMenu` que tem ações secundárias. */
export function ToolbarOverflowMenu() {
  const actions = use(ToolbarMenuActionsContext);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon" aria-label="Mais ações" className="md:hidden">
          <LuEllipsisVertical className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        {actions.map((action) => (
          <DropdownMenuItem
            key={action.label}
            disabled={action.disabled}
            onSelect={action.onSelect}
          >
            {action.icon}
            {action.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

const MODE_CHOICES = [
  { mode: "pages", label: "Páginas numeradas", hint: "Navega por número de página" },
  { mode: "infinite", label: "Rolagem contínua", hint: "Carrega mais ao chegar no fim" },
] as const;

interface ListOptionsMenuProps {
  mode: ListMode;
  onModeChange: (mode: ListMode) => void;
  /** Omitido = a tela não tem faixa de recentes, e a opção some. */
  showRecents?: boolean;
  onShowRecentsChange?: (show: boolean) => void;
}

/** ⋮ no fim da toolbar: preferências de exibição da tela, guardadas por navegador. */
export function ListOptionsMenu({
  mode,
  onModeChange,
  showRecents,
  onShowRecentsChange,
}: ListOptionsMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon" aria-label="Opções da lista">
          <LuEllipsisVertical className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <ToolbarMenuActionItems />
        <DropdownMenuLabel>Exibição</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={mode}
          onValueChange={(next) => onModeChange(next === "infinite" ? "infinite" : "pages")}
        >
          {MODE_CHOICES.map((choice) => (
            // Bolinha de rádio sempre desenhada (vazia/cheia): só o check do item marcado não
            // dizia que as duas opções são "uma OU outra" (feedback 2026-10-09).
            <DropdownMenuRadioItem
              key={choice.mode}
              value={choice.mode}
              className="group items-start pr-2 [&_[data-slot=dropdown-menu-radio-item-indicator]]:hidden"
            >
              <span
                aria-hidden
                className="border-muted-foreground/50 group-data-[state=checked]:border-primary mt-0.5 flex size-3.5 shrink-0 items-center justify-center rounded-full border"
              >
                <span className="bg-primary size-1.5 rounded-full opacity-0 group-data-[state=checked]:opacity-100" />
              </span>
              <span className="min-w-0">
                <span className="block font-medium">{choice.label}</span>
                <span className="text-muted-foreground block text-[0.6875rem]">{choice.hint}</span>
              </span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        {showRecents !== undefined && onShowRecentsChange && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuCheckboxItem
              checked={showRecents}
              onCheckedChange={(checked) => onShowRecentsChange(checked === true)}
            >
              Mostrar abertos recentemente
            </DropdownMenuCheckboxItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

interface ListSummaryProps {
  /** Páginas: o recorte "21–40"; infinito: quantos já foram carregados. */
  mode: ListMode;
  loaded: number;
  total: number;
  page: number;
  pageSize: number;
  countLabel?: (total: number) => string;
}

/**
 * Totais NO TOPO da lista — o rodapé da paginação não é visível sem rolar, e o fim do
 * infinito nunca chega. Páginas: "21–40 de 1.355 veículos"; infinito: "48 de 1.355 veículos".
 */
export function ListSummary({ mode, loaded, total, page, pageSize, countLabel }: ListSummaryProps) {
  const totalLabel = countLabel ? countLabel(total) : formatCount(total);
  const shown =
    mode === "infinite"
      ? formatCount(loaded)
      : (() => {
          const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
          const to = Math.min(page * pageSize, total);
          return from === to ? formatCount(from) : `${formatCount(from)}–${formatCount(to)}`;
        })();
  return (
    <p aria-live="polite" className="text-muted-foreground text-sm tabular-nums">
      {shown} de {totalLabel}
    </p>
  );
}

/**
 * Fim da lista infinita: sentinela (carrega quando o usuário ROLA até aqui) + "Carregar
 * mais" (lista que não enche a tela não rola; teclado; leitor de tela).
 */
export function InfiniteListLoader({ controls }: { controls: InfiniteListControls }) {
  const sentinelRef = useInfiniteScrollSentinel(controls);
  if (!controls.hasNextPage) return null;
  return (
    <div ref={sentinelRef} className="flex justify-center">
      <Button
        variant="outline"
        disabled={controls.isFetchingNextPage}
        onClick={() => controls.fetchNextPage()}
      >
        {controls.isFetchingNextPage ? "Carregando…" : "Carregar mais"}
      </Button>
    </div>
  );
}

/** Quantos cabem por largura: 2 no celular, 3 no tablet, 5 a partir de `lg`. */
const RECENT_VISIBILITY = ["", "", "max-sm:hidden", "max-lg:hidden", "max-lg:hidden"] as const;

interface RecentlyOpenedStripProps {
  entries: RecentEntry[];
  onOpen: (entry: RecentEntry) => void;
  /** "Limpar" no cabeçalho da própria faixa — onde o olho já está. */
  onClear: () => void;
}

/**
 * Atalho para os últimos abertos a partir desta tela. O caso real: buscou uma placa, abriu
 * um carro lá do fim da lista, voltou — e quer reabrir sem lembrar qual era nem buscar de
 * novo. Cards mínimos (miniatura + título + detalhe), em grade (sem rolagem lateral).
 */
export function RecentlyOpenedStrip({ entries, onOpen, onClear }: RecentlyOpenedStripProps) {
  if (entries.length === 0) return null;
  return (
    <section aria-label="Abertos recentemente" className="space-y-1.5">
      <div className="flex items-center gap-3">
        <p className="text-muted-foreground flex items-center gap-1.5 text-xs font-medium">
          <LuHistory className="size-3.5" />
          Abertos recentemente
        </p>
        <button
          type="button"
          onClick={onClear}
          className="text-muted-foreground hover:text-foreground focus-visible:ring-ring rounded text-xs underline-offset-2 outline-hidden hover:underline focus-visible:ring-2"
        >
          Limpar
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {entries.map((entry, index) => (
          <button
            key={entry.id}
            type="button"
            onClick={() => onOpen(entry)}
            className={cn(
              "bg-card hover:bg-muted/60 focus-visible:ring-ring flex min-w-0 items-center gap-2 rounded-lg border p-1.5 text-left outline-hidden transition-colors focus-visible:ring-2",
              RECENT_VISIBILITY[index]
            )}
          >
            {entry.imageUrl ? (
              <img
                src={entry.imageUrl}
                alt=""
                className="size-9 shrink-0 rounded-md object-cover"
                loading="lazy"
              />
            ) : (
              <span className="bg-muted size-9 shrink-0 rounded-md" aria-hidden />
            )}
            <span className="min-w-0">
              <span className="block truncate text-xs font-medium">{entry.title}</span>
              {entry.subtitle && (
                <span className="text-muted-foreground block truncate text-[0.6875rem]">
                  {entry.subtitle}
                </span>
              )}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
