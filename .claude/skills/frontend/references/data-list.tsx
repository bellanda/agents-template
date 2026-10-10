import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { InfiniteListLoader, ListSummary } from "@/components/ui/list-options";
import { ListPagination } from "@/components/ui/list-pagination";
import type { InfiniteListControls } from "@/hooks/useCollectionList";
import { cn } from "@/lib/utils";
import { useCallback, useRef, type MouseEvent, type ReactNode } from "react";
import type { IconType } from "react-icons";
import { LuEllipsisVertical, LuTriangleAlert } from "react-icons/lu";
import { errorMessage } from "@/lib/api/error-message";

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
  /** Motivo (pt-BR) pelo qual a ação não pode ser usada nesta linha; a ação fica visível mas
   *  desabilitada e o motivo aparece como `title` (dica ao passar o mouse / segurar). */
  disabledReason?: (item: T) => string | undefined;
}

export interface DataListSelection {
  selectedIds: ReadonlySet<string>;
  /** Recebe o `getRowId` da linha — a tela é dona do Set (ver `useListSelection`). */
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

  /** Spread direto do `usePagedList` / `useCollectionList`. */
  isLoading: boolean;
  isFetching: boolean;
  total: number;
  page: number;
  pageSize: number;
  pageCount: number;
  /** A página mora na URL e a tela é dona dela — o DataList só pede a troca. */
  onPageChange: (page: number) => void;
  /**
   * Presente = modo rolagem contínua (vem no spread do `useCollectionList`): o fim da lista
   * vira sentinela + "Carregar mais" e `page`/`onPageChange` ficam ociosos. Ausente =
   * paginação numerada. Nos dois o resumo "X de Y" fica no TOPO da lista.
   */
  infinite?: InfiniteListControls;
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
   * Seleção múltipla — opcional, e todo o comportamento novo fica atrás dela: as
   * telas que não passam `selection` renderizam exatamente como antes.
   *
   * O checkbox é absoluto sobre o CARD, o que cobre `grid`, `stack` e o mobile de
   * `table` de uma vez, sem tocar em nenhum `renderCard` de tela. A tabela do
   * desktop fica de fora desta rodada: uma coluna a mais mexeria no header das
   * ~15 telas que usam o default, e o consumidor real (estoque de veículos) é
   * `variant="grid"`, que não tem tabela.
   */
  selection?: DataListSelection;
  /** Query falhou: mostra o bloco de erro NO LUGAR do estado vazio.
   *  Com `{...usePagedList(...)}` os três chegam de graça pelo spread. */
  isError?: boolean;
  error?: unknown;
  refetch?: () => unknown;
  onRetry?: () => void;
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
              disabled={!!action.disabledReason?.(item)}
              title={action.disabledReason?.(item)}
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
      {available.map((action) => {
        const disabledReason = action.disabledReason?.(item);
        return (
          // O `span` leva o `title`: botão desabilitado não dispara hover/foco no navegador.
          <span key={action.id} title={disabledReason} className="inline-flex">
            <Button
              variant="ghost"
              size="icon"
              aria-label={action.label}
              disabled={!!disabledReason}
              onClick={() => action.onSelect(item)}
            >
              <action.icon className={cn("size-4", action.destructive && "text-destructive")} />
            </Button>
          </span>
        );
      })}
    </>
  );
}

/** "Limpar filtros" substitui a ação do vazio quando o vazio é efeito de filtro ativo. */
function emptyStateAction({
  isFiltered,
  onClearFilters,
  action,
}: {
  isFiltered?: boolean;
  onClearFilters?: () => void;
  action?: ReactNode;
}): ReactNode {
  if (!isFiltered || !onClearFilters) return action;
  return (
    <Button variant="outline" size="sm" onClick={onClearFilters}>
      Limpar filtros
    </Button>
  );
}

/**
 * Estado de ERRO da lista — nunca o estado vazio.
 *
 * Sem ele, query que falha (rede fora, 500, 403 numa tela que o gate do front
 * deixou passar) caía em `items = []` e a tela dizia "Nenhum veículo encontrado".
 * O usuário concluía que o estoque estava vazio e seguia em frente; o erro
 * existia só no console. Coleção vazia e coleção que não carregou são fatos
 * diferentes e precisam de telas diferentes.
 */
function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-16 text-center" role="alert">
      <LuTriangleAlert className="text-destructive h-6 w-6" aria-hidden />
      <p className="text-sm font-medium">Não foi possível carregar esta lista</p>
      <p className="text-muted-foreground max-w-prose text-xs">{errorMessage(error)}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Tentar novamente
        </Button>
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
    (column) => column !== primary && (column.role === "meta" || column.role === undefined)
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
                selection && "relative pl-14"
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
  /** Query falhou: mostra o bloco de erro NO LUGAR do estado vazio.
   *  Com `{...usePagedList(...)}` os três chegam de graça pelo spread. */
  isError?: boolean;
  error?: unknown;
  refetch?: () => unknown;
  onRetry?: () => void;
  className?: string;
}

/**
 * Tabela BOUNDED: o mesmo par tabela-desktop / card-mobile do `DataList`, sem
 * paginação, sem busca e sem sentinela.
 *
 * É para o conjunto que já veio inteiro e cujo tamanho o domínio limita — itens
 * de um orçamento, parcelas de um título, ranking de mecânicos do mês, versões
 * de um agente. Coleção que CRESCE com o uso é `DataList` + `usePagedList`;
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
  isError,
  error,
  refetch,
  onRetry,
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

  if (isError) {
    return (
      <div className={cn("rounded-md border", className)}>
        <ErrorState error={error} onRetry={onRetry ?? (refetch ? () => refetch() : undefined)} />
      </div>
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
 * ≥768px) e a pilha de cards (mobile). Dois modos de navegação sobre o mesmo endpoint,
 * escolhidos por tela (`useCollectionList` + `useListMode`): paginação numerada (default)
 * ou rolagem contínua (`infinite`). Os dois mostram "carregados de total".
 */
export function DataList<T>({
  items,
  columns,
  getRowId,
  actions = [],
  onRowClick,
  isLoading,
  isFetching,
  total,
  page,
  pageSize,
  pageCount,
  onPageChange,
  infinite,
  isFiltered,
  emptyTitle,
  emptyDescription,
  emptyAction,
  onClearFilters,
  countLabel,
  renderCard,
  variant = "table",
  selection,
  isError,
  error,
  refetch,
  onRetry,
  className,
}: DataListProps<T>) {
  const topRef = useRef<HTMLDivElement>(null);
  // `nearest` só rola quando o topo da lista já saiu da tela (clicou "próxima" lá
  // embaixo); com a lista inteira à vista, trocar de página não mexe no scroll.
  const changePage = useCallback(
    (next: number) => {
      onPageChange(next);
      topRef.current?.scrollIntoView({ block: "nearest" });
    },
    [onPageChange]
  );
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

  if (isError) {
    return (
      <div className={cn("rounded-md border", className)}>
        <ErrorState error={error} onRetry={onRetry ?? (refetch ? () => refetch() : undefined)} />
      </div>
    );
  }

  // Página que sumiu embaixo do usuário (exclusão, filtro de outra aba, link velho):
  // não é coleção vazia — há itens, só não nesta página.
  if (items.length === 0 && page > 1 && total > 0) {
    return (
      <div className={cn("rounded-md border", className)}>
        <EmptyState
          title={`Esta página não existe mais — a lista tem ${pageCount} página${pageCount === 1 ? "" : "s"}.`}
          action={
            <Button variant="outline" size="sm" onClick={() => changePage(pageCount)}>
              Ir para a página {pageCount}
            </Button>
          }
        />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className={cn("rounded-md border", className)}>
        <EmptyState
          title={emptyTitle}
          description={emptyDescription}
          action={emptyStateAction({ isFiltered, onClearFilters, action: emptyAction })}
        />
      </div>
    );
  }

  // Troca de página/filtro escurece a página atual (mantida pelo `keepPreviousData`
  // do `usePagedList`) até a próxima chegar, em vez de piscar um skeleton.
  const dimming = isFetching && !isLoading;

  return (
    <div ref={topRef} className={cn("scroll-mt-20 space-y-3", className)}>
      <ListSummary
        mode={infinite ? "infinite" : "pages"}
        loaded={items.length}
        total={total}
        page={page}
        pageSize={pageSize}
        countLabel={countLabel}
      />

      <div
        aria-busy={dimming}
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

      {infinite ? (
        <InfiniteListLoader controls={infinite} />
      ) : (
        <ListPagination
          page={page}
          pageCount={pageCount}
          pageSize={pageSize}
          total={total}
          countLabel={countLabel}
          onPageChange={changePage}
          hideRange
          className="sm:justify-end"
        />
      )}
    </div>
  );
}
