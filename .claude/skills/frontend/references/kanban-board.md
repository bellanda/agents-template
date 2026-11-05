# Quadro kanban (colunas arrastáveis, cards por coluna)

> Reference do gate `frontend`. Abra ANTES de construir um quadro de funil/etapas com arrastar-e-soltar.
> Canônico: **kailos** `routes/_authenticated/organizations/$id/crm/quadro.tsx` +
> `components/crm/board/*`. Tela de lista comum -> `list-screen.md` (o quadro é a visão do gerente, a
> lista é a do dia a dia). Tempo real do quadro -> `realtime-and-push-actions.md`. CRM 2030, 2026-11-05.

## Anatomia (frontend)

| Peça | Arquivo | Regra |
| ---- | ------- | ----- |
| Rota | `crm/quadro.tsx` | `beforeLoad` síncrono com a permissão de gerência; `validateSearch: parseBoardSearch`; filtros/seleção/ações em lote aqui. |
| Quadro | `board/Board.tsx` | `DndContext` + `collisionDetection` (`pointerWithin`, cai em `rectIntersection` p/ teclado/toque) + `DragOverlay` com o card fantasma. Colunas = droppable, cards = só draggable. |
| Coluna | `board/BoardColumn.tsx` | `useDroppable({id: key, disabled})`, `memo`, cabeçalho recolhível (fechadas começam recolhidas só com a contagem), "carregar mais" por rolagem até o fim (`NEAR_END_PX`) **e** botão explícito. Mobile: `w-[85%] snap-start`, container query `@xl/main:w-72`. |
| Card | `board/BoardCard.tsx` | `memo`; `useDraggable` com `data: {item, columnKey}`; reutiliza o card da lista. |
| Regras do drop | `board/board-rules.ts` | `decideDrop(from,to)` **puro**: `noop` / `move` / `sold` / `lost` (abrem diálogo) / `refuse` (toast com motivo). Testado sem simular ponteiro. |
| Diálogos terminais | `board/StageDialogs.tsx` | Coluna terminal (vendido/perdido) **nunca** muda no drop direto: abre `FormDialog` pedindo o dado obrigatório (venda registrada / motivo). Só PATCHa após confirmar. |
| Cache | `board/board-cache.ts` | helpers puros sobre o `BoardResponse`: `moveCard` (otimista + patch de SSE), rollback por snapshot, anexar página, contagens das duas colunas. |
| Relógio | `board/BoardClock.tsx` | UM `useNow(30s)` no provider; só as folhas (`SlaBar`) re-renderizam; os `children` mantêm identidade, então os cards memoizados NÃO re-renderizam pelo relógio. |
| Filtros | `board/board-search.ts` + `BoardFilters.tsx` | tudo na URL (`validateSearch`), `selection.clear()` ao mudar filtro. |
| Lote | `BulkDialogs.tsx` + `ui/bulk-actions-menu` + `useListSelection` | `versions` por id (trava otimista): o que mudou desde que abriu volta como `stale_version` e o resumo agrupa os ignorados por motivo. Teto `MAX_BULK_IDS=200`. |

### Sensores

`lib/dnd/row-drag-sensors.ts` (`useRowDragSensors`): arrasta o card inteiro; mouse com distância mínima
(6 px, clique continua clique), toque com long-press 250 ms (não sequestra a rolagem; **sem**
`touch-action: none`), teclado na alça. `INTERACTIVE_SELECTOR` (input, button, a, label,
`[data-no-drag]`...) nunca inicia arrasto. Decisão do usuário 2026-10-02.

### Invariantes

- Mover = **PATCH otimista com `expectedVersion`** e rollback do snapshot se falhar (teste dedicado).
- Coluna "automática" (ex.: repescagem) é `droppable: false` e o drop é `refuse`; reabrir encerrado
  também é recusado (motivo em pt-BR).
- O Quadro registra `registerCrmPatchListener` num `useEffect` (cleanup devolvido): o evento move o
  card entre colunas e corrige as duas contagens; patch que traz dono novo faz refetch (não adivinha nome).
- Nada de `limit: 500`: cada coluna tem sua página.

## Backend

- `routes/crm/board.py` (`GET /board`, `GET /board/columns/{key}`, `POST /attendances/bulk`, export CSV);
  montadas ANTES do router `/{id}` (UUID capturaria `bulk`/`export.csv` -> 422).
- **Keyset por coluna** `(temperature_score DESC, id ASC)` = a ordem do índice do quadro; cursor opaco
  base64 `"{score}:{id}"` (`services/crm/board.py`); pede `limit+1` (sentinela `has_more`).
- **Contagens em UMA instrução**: três `GROUP BY` index-only unidos por `UNION ALL` (índice do quadro,
  da repescagem e dos fechados no período). Nada de `COUNT(*) OVER()`.
- Fechados: só os do período (default 30 dias). CSV: teto `EXPORT_MAX_ROWS` e neutraliza prefixos
  `= + - @` (CSV injection).
- Testes: `backend/tests/crm/test_board_api.py` — `columns_counts_keyset_and_filters`,
  `permissions_and_tenancy`, `bulk_reassign_labels_campaign_and_skips`, `export_csv...`,
  **`board_queries_use_indexes`** e `board_page_query..._is_seq_scan_free` (EXPLAIN: sem seq scan).
- Front: `board/__tests__/board.test.tsx` (decideDrop, patch de SSE move a coluna e as contagens, dono
  novo refaz, diálogos só PATCHam após confirmar, rollback, 1 intervalo p/ N barras, card memoizado).
