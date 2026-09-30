import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useInfiniteScrollSentinel } from "@/hooks/useInfiniteList";
import type { MouseEvent, ReactNode } from "react";
import type { IconType } from "react-icons";
import { LuEllipsisVertical, LuLoader } from "react-icons/lu";

/**
 * Papel da coluna no card mobile — é isto que dispensa um segundo renderer.
 *   primary   → título do card (EXATAMENTE uma coluna deve ter)
 *   secondary → subtítulo muted logo abaixo do título
 *   badge     → chip no canto superior direito (status)
 *   meta      → linha "rótulo | valor" no corpo do card  ← default
 *   hidden    → só desktop (coluna larga, notas, texto longo)
 */
export type DataListColumnRole = "primary" | "secondary" | "badge" | "meta" | "hidden";

export interface DataListColumn<T> {
  /** Estável — vira React key da célula. */
  id: string;
  header: ReactNode;
  cell: (item: T) => ReactNode;
  role?: DataListColumnRole;
  /** Override SÓ do conteúdo no card (versão curta de uma célula larga). */
  renderCard?: (item: T) => ReactNode;
  /** Classe do `<td>`/`<th>` no DESKTOP — densidade md→2xl (`"hidden lg:table-cell"`). */
  className?: string;
  headClassName?: string;
}

export interface DataListAction<T> {
  id: string;
  label: string;
  icon: IconType;
  onSelect: (item: T) => void;
  destructive?: boolean;
  /** Esconde a ação por linha (ex.: não pode excluir OS já entregue). */
  hidden?: (item: T) => boolean;
}

export interface DataListSelection {
  selectedIds: ReadonlySet<string>;
  /** Recebe o `getRowId` da linha — a tela é dona do Set (ver `use-list-selection.ts`). */
  onToggle: (id: string) => void;
}

export interface DataListProps<T> {
  items: T[];
  columns: DataListColumn<T>[];
  getRowId: (item: T) => string;
  /**
   * Ações por linha. Filtre por permissão NO CALLER —
   * `actions={[...(can(P.UPDATE) ? [edit] : [])]}`. O componente é vendorado nos
   * 5 projetos e cada um tem um hook de permissão diferente.
   */
  actions?: DataListAction<T>[];
  onRowClick?: (item: T) => void;

  /** Spread direto do `useInfiniteList`. */
  isLoading: boolean;
  isFetching: boolean;
  isFetchingNextPage: boolean;
  hasNextPage: boolean;
  fetchNextPage: () => void;
  total: number;

  /** Distingue "nada cadastrado" de "nada encontrado". */
  isFiltered?: boolean;
  emptyTitle: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  onClearFilters?: () => void;

  countLabel?: (total: number) => string;
  /** Escotilha total: ignora os roles e desenha o card inteiro. */
  renderCard?: (item: T, context: { actions: ReactNode }) => ReactNode;
  /**
   * `"table"` (default) → tabela no desktop, card no mobile.
   * `"grid"` → card em TODOS os breakpoints, em grade responsiva. É para coleção
   * cujo conteúdo É visual (veículo com foto, pedido com miniatura): espremer a
   * imagem numa célula de tabela desperdiça exatamente o que se veio ver.
   * `"stack"` → card full-width empilhado em TODOS os breakpoints. É para o item
   * que expande no lugar (fila de aprovação com documentos, log com payload):
   * não cabe numa linha de tabela nem numa coluna de grade.
   * `columns` continua sendo a fonte dos roles do card — o `variant` só troca o
   * container. Numa coleção textual, sair do default é regressão.
   */
  variant?: "table" | "grid" | "stack";
  /**
   * Seleção múltipla — opcional; tela que não passa `selection` renderiza igual.
   * O estado e as ações em lote moram na tela (`useListSelection` + `BulkActionsMenu`
   * no slot `actions` do `ListToolbar`); a lista só desenha o checkbox.
   *
   * O checkbox é absoluto sobre o CARD, o que cobre `grid`, `stack` e o mobile de
   * `table` de uma vez, sem tocar em nenhum `renderCard` de tela. A tabela do
   * desktop fica sem checkbox: seleção em lote é de coleção visual (estoque em
   * `variant="grid"`), e uma coluna a mais mexeria no header de toda tela default.
   */
  selection?: DataListSelection;
  className?: string;
}

/** Quantas linhas de esqueleto na primeira carga. */
const SKELETON_ROWS = 5;
/** Acima disto as ações viram DropdownMenu em vez de botões inline. */
const INLINE_ACTIONS_MAX = 2;

/** True quando o clique de linha caiu num elemento interativo interno. */
function isInteractiveClick(event: MouseEvent<HTMLElement>): boolean {
  if (!(event.target instanceof Element)) return false;
  return event.target.closest("a, button, input, label, [role='menuitem']") !== null;
}

function visibleActions<T>(actions: DataListAction<T>[], item: T) {
  return actions.filter((action) => !action.hidden?.(item));
}

function ActionButtons<T>({ actions, item }: { actions: DataListAction<T>[]; item: T }) {
  const available = visibleActions(actions, item);
  if (available.length === 0) return null;

  if (available.length > INLINE_ACTIONS_MAX) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="Ações">
            <LuEllipsisVertical className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {available.map((action) => (
            <DropdownMenuItem
              key={action.id}
              variant={action.destructive ? "destructive" : undefined}
              onSelect={() => action.onSelect(item)}
            >
              <action.icon className="size-4" />
              {action.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  return (
    <>
      {available.map((action) => (
        <Button
          key={action.id}
          variant="ghost"
          size="icon"
          aria-label={action.label}
          onClick={() => action.onSelect(item)}
        >
          <action.icon className={cn("size-4", action.destructive && "text-destructive")} />
        </Button>
      ))}
    </>
  );
}

function EmptyState({
  title,
  description,
  action,
  onClearFilters,
  isFiltered,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  onClearFilters?: () => void;
  isFiltered?: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
      <p className="text-muted-foreground text-sm">{title}</p>
      {description && <p className="text-muted-foreground text-xs">{description}</p>}
      {isFiltered && onClearFilters ? (
        <Button variant="outline" size="sm" onClick={onClearFilters}>
          Limpar filtros
        </Button>
      ) : (
        action
      )}
    </div>
  );
}

/**
 * Corpo compartilhado por `DataList` e `StaticDataList`: a tabela do desktop e a
 * pilha de cards do mobile, a partir da MESMA definição de coluna.
 *
 * O switch é CSS (`hidden md:block` / `md:hidden`), NÃO `useIsMobile()`: o hook
 * resolve em `useEffect`, então no celular a tabela pisca no primeiro paint e a
 * subárvore inteira remonta a cada resize cruzando 768px — derrubando o
 * IntersectionObserver junto.
 */
function ResponsiveRows<T>({
  items,
  columns,
  getRowId,
  actions,
  onRowClick,
  renderCard,
  variant,
  tableFooter,
  selection,
}: {
  items: T[];
  columns: DataListColumn<T>[];
  getRowId: (item: T) => string;
  actions: DataListAction<T>[];
  onRowClick?: (item: T) => void;
  renderCard?: (item: T, context: { actions: ReactNode }) => ReactNode;
  variant: "table" | "grid" | "stack";
  tableFooter?: ReactNode;
  selection?: DataListSelection;
}) {
  const cardsOnly = variant !== "table";
  const cardsClassName = cardsClassNameFor(variant);

  const hasActions = actions.length > 0;
  // Desktop mostra TODAS as colunas — inclusive `role: "hidden"`, que significa
  // "só desktop". A densidade por breakpoint continua no `className` da coluna.
  const desktopColumns = columns;

  const primary = columns.find((column) => column.role === "primary") ?? columns[0];
  const secondary = columns.filter((column) => column.role === "secondary");
  const badges = columns.filter((column) => column.role === "badge");
  const meta = columns.filter(
    (column) => column !== primary && (column.role === "meta" || column.role === undefined),
  );

  const cardContent = (column: DataListColumn<T>, item: T) =>
    column.renderCard ? column.renderCard(item) : column.cell(item);

  const rowClick = (item: T) => (event: MouseEvent<HTMLElement>) => {
    if (!onRowClick || isInteractiveClick(event)) return;
    onRowClick(item);
  };

  /**
   * Checkbox de seleção sobre o card. O `<label>` de 44px é o alvo de toque —
   * o quadrado do Radix sozinho tem 16px e não se acerta com o dedo.
   *
   * Marcar NÃO dispara `onRowClick`: `isInteractiveClick` já fecha em `label` e
   * em `button`, e o Radix Checkbox é um `<button role="checkbox">`.
   */
  const selectionBox = (id: string) =>
    selection ? (
      <label
        aria-label="Selecionar"
        className="absolute top-1 left-1 z-10 flex size-11 cursor-pointer items-center justify-center"
      >
        <Checkbox
          checked={selection.selectedIds.has(id)}
          onCheckedChange={() => selection.onToggle(id)}
          className="bg-background/90 border-foreground/30 shadow-sm"
        />
      </label>
    ) : null;

  return (
    <>
      {/* ── Desktop: tabela (ausente em `variant="grid"`/`"stack"`) ─────── */}
      {!cardsOnly && (
        <div className="hidden rounded-md border md:block">
          <Table>
            <TableHeader>
              <TableRow>
                {desktopColumns.map((column) => (
                  <TableHead key={column.id} className={column.headClassName ?? column.className}>
                    {column.header}
                  </TableHead>
                ))}
                {hasActions && <TableHead className="w-24" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow
                  key={getRowId(item)}
                  className={cn(onRowClick && "cursor-pointer")}
                  onClick={rowClick(item)}
                >
                  {desktopColumns.map((column) => (
                    <TableCell key={column.id} className={column.className}>
                      {column.cell(item)}
                    </TableCell>
                  ))}
                  {hasActions && (
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <ActionButtons actions={actions} item={item} />
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
            {tableFooter}
          </Table>
        </div>
      )}

      {/* ── Cards: mobile sempre, todos os breakpoints em `grid` ────────── */}
      <div className={cardsClassName}>
        {items.map((item) => {
          const actionsNode = hasActions ? (
            <div className="flex justify-end gap-1">
              <ActionButtons actions={actions} item={item} />
            </div>
          ) : null;

          if (renderCard) {
            return (
              <div
                key={getRowId(item)}
                onClick={rowClick(item)}
                className={cn(selection && "relative")}
              >
                {selectionBox(getRowId(item))}
                {renderCard(item, { actions: actionsNode })}
              </div>
            );
          }

          return (
            // Card é um <div>, NUNCA um <a>: os botões de ação ficariam
            // aninhados dentro de âncora (HTML inválido, quebra no Safari). O
            // alvo focável de verdade é o <Link> que a coluna `primary` renderiza.
            <div
              key={getRowId(item)}
              onClick={rowClick(item)}
              className={cn(
                "bg-card rounded-lg border p-4",
                onRowClick && "active:bg-muted/50 cursor-pointer",
                // O checkbox flutua sobre o canto; sem a calha o título passaria por baixo.
                selection && "relative pl-14",
              )}
            >
              {selectionBox(getRowId(item))}
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{cardContent(primary, item)}</div>
                  {secondary.map((column) => (
                    <div key={column.id} className="text-muted-foreground truncate text-xs">
                      {cardContent(column, item)}
                    </div>
                  ))}
                </div>
                {badges.length > 0 && (
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    {badges.map((column) => (
                      <div key={column.id}>{cardContent(column, item)}</div>
                    ))}
                  </div>
                )}
              </div>

              {meta.length > 0 && (
                <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-t pt-3 text-xs">
                  {meta.map((column) => (
                    <div key={column.id} className="contents">
                      <dt className="text-muted-foreground">{column.header}</dt>
                      <dd className="truncate text-right">{cardContent(column, item)}</dd>
                    </div>
                  ))}
                </dl>
              )}

              {actionsNode && <div className="mt-2 border-t pt-2">{actionsNode}</div>}
            </div>
          );
        })}
      </div>
    </>
  );
}

function LoadingRows<T>({
  columns,
  hasActions,
  cardsOnly,
  cardsClassName,
  className,
}: {
  columns: DataListColumn<T>[];
  hasActions: boolean;
  cardsOnly: boolean;
  cardsClassName: string;
  className?: string;
}) {
  const columnCount = columns.length + (hasActions ? 1 : 0);
  return (
    <div className={cn("space-y-3", className)}>
      {!cardsOnly && (
        <div className="hidden rounded-md border md:block">
          <Table>
            <TableHeader>
              <TableRow>
                {columns.map((column) => (
                  <TableHead key={column.id} className={column.headClassName ?? column.className}>
                    {column.header}
                  </TableHead>
                ))}
                {hasActions && <TableHead className="w-24" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: SKELETON_ROWS }, (_, index) => (
                <TableRow key={index}>
                  {Array.from({ length: columnCount }, (_, cell) => (
                    <TableCell key={cell}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <div className={cardsClassName}>
        {Array.from({ length: SKELETON_ROWS }, (_, index) => (
          <Skeleton key={index} className="h-28 w-full rounded-lg" />
        ))}
      </div>
    </div>
  );
}

/** Classe do container de cards — compartilhada pelos dois componentes. */
function cardsClassNameFor(variant: "table" | "grid" | "stack") {
  return variant === "grid"
    ? "grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
    : cn("space-y-3", variant === "table" && "md:hidden");
}

export interface StaticDataListProps<T> {
  items: T[];
  columns: DataListColumn<T>[];
  getRowId: (item: T) => string;
  actions?: DataListAction<T>[];
  onRowClick?: (item: T) => void;
  renderCard?: (item: T, context: { actions: ReactNode }) => ReactNode;
  variant?: "table" | "grid" | "stack";
  emptyTitle: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  isLoading?: boolean;
  /**
   * `<TableFooter>` do desktop (linha de totais). NÃO tem equivalente no card —
   * o total do mobile é responsabilidade do caller, acima ou abaixo da lista.
   */
  tableFooter?: ReactNode;
  className?: string;
}

/**
 * Tabela BOUNDED: o mesmo par tabela-desktop / card-mobile do `DataList`, sem
 * paginação, sem busca e sem sentinela.
 *
 * É para o conjunto que já veio inteiro e cujo tamanho o domínio limita — itens
 * de um orçamento, parcelas de um título, ranking de mecânicos do mês, versões
 * de um agente. Coleção que CRESCE com o uso é `DataList` + `useInfiniteList`;
 * usar este aqui nela é fetch-all disfarçado.
 */
export function StaticDataList<T>({
  items,
  columns,
  getRowId,
  actions = [],
  onRowClick,
  renderCard,
  variant = "table",
  emptyTitle,
  emptyDescription,
  emptyAction,
  isLoading,
  tableFooter,
  className,
}: StaticDataListProps<T>) {
  if (isLoading) {
    return (
      <LoadingRows
        columns={columns}
        hasActions={actions.length > 0}
        cardsOnly={variant !== "table"}
        cardsClassName={cardsClassNameFor(variant)}
        className={className}
      />
    );
  }

  if (items.length === 0) {
    return (
      <div className={cn("rounded-md border", className)}>
        <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
      </div>
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <ResponsiveRows
        items={items}
        columns={columns}
        getRowId={getRowId}
        actions={actions}
        onRowClick={onRowClick}
        renderCard={renderCard}
        variant={variant}
        tableFooter={tableFooter}
      />
    </div>
  );
}

/**
 * Lista canônica de COLEÇÃO: uma definição de coluna renderiza a tabela (desktop,
 * ≥768px) e a pilha de cards (mobile). Scroll infinito de 10 em 10.
 */
export function DataList<T>({
  items,
  columns,
  getRowId,
  actions = [],
  onRowClick,
  isLoading,
  isFetching,
  isFetchingNextPage,
  hasNextPage,
  fetchNextPage,
  total,
  isFiltered,
  emptyTitle,
  emptyDescription,
  emptyAction,
  onClearFilters,
  countLabel,
  renderCard,
  variant = "table",
  selection,
  className,
}: DataListProps<T>) {
  const sentinelRef = useInfiniteScrollSentinel({
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  });
  // Fora do default o card é a ÚNICA árvore: some o `md:hidden` que o esconderia no
  // desktop e a tabela sai do DOM. Esconder a tabela por CSS não bastaria — o React
  // renderiza a subárvore inteira do mesmo jeito (cada `cell` de cada linha roda duas
  // vezes) e todo texto passa a aparecer duplicado para leitor de tela e para teste.
  const cardsOnly = variant !== "table";

  if (isLoading) {
    return (
      <LoadingRows
        columns={columns}
        hasActions={actions.length > 0}
        cardsOnly={cardsOnly}
        cardsClassName={cardsClassNameFor(variant)}
        className={className}
      />
    );
  }

  if (items.length === 0) {
    return (
      <div className={cn("rounded-md border", className)}>
        <EmptyState
          title={emptyTitle}
          description={emptyDescription}
          action={emptyAction}
          onClearFilters={onClearFilters}
          isFiltered={isFiltered}
        />
      </div>
    );
  }

  // Refetch de filtro/sort escurece as linhas atuais em vez de trocar por
  // skeleton (não há `keepPreviousData` em infinite query — ver useInfiniteList).
  const dimming = isFetching && !isFetchingNextPage;

  return (
    <div className={cn("space-y-3", className)}>
      <div
        aria-busy={isFetchingNextPage}
        className={cn("transition-opacity", dimming && "pointer-events-none opacity-60")}
      >
        <ResponsiveRows
          items={items}
          columns={columns}
          getRowId={getRowId}
          actions={actions}
          onRowClick={onRowClick}
          renderCard={renderCard}
          variant={variant}
          selection={selection}
        />
      </div>

      {/* ── Rodapé: contagem + carregar mais ────────────────────────────────
          O <Button> é o mecanismo PRIMÁRIO — leitor de tela e teclado não
          disparam interseção visual, e um container que não rola (viewport curta,
          usuário com zoom) nunca chega no sentinel. O observer só o aperta.
          Um sentinel só, FORA das duas árvores responsivas: nó dentro de
          `display:none` nunca intersecta e morreria num dos breakpoints. */}
      <div className="flex flex-col items-center gap-2">
        <p aria-live="polite" className="text-muted-foreground text-xs">
          {isFetchingNextPage
            ? "Carregando mais…"
            : countLabel
              ? `${items.length} de ${countLabel(total)}`
              : `${items.length} de ${total}`}
        </p>
        {hasNextPage && (
          <>
            <div ref={sentinelRef} aria-hidden className="h-10 w-full" />
            <Button
              variant="outline"
              size="sm"
              onClick={fetchNextPage}
              disabled={isFetchingNextPage}
            >
              {isFetchingNextPage && <LuLoader className="mr-2 size-4 animate-spin" />}
              Carregar mais
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
