# Tela de lista — DataList, scroll infinito, filtros e ordenação

> Reference do gate `frontend` (item 8f). Anatomia canônica de qualquer tela que lista registros.
> Componentes: `references/data-list.tsx`, `references/list-toolbar.tsx`,
> `references/use-infinite-list.ts`, `references/bulk-actions-menu.tsx`,
> `references/use-list-selection.ts` (vendorados em `ui/data-list.tsx`, `ui/list-toolbar.tsx`,
> `hooks/useInfiniteList.ts`, `ui/bulk-actions-menu.tsx`, `hooks/useListSelection.ts`). Contrato de backend: gate `database` → `references/list-pagination.md`.

## Anatomia (não tem variação)

```
<ListToolbar>        busca + filtros + ordenação + [Ações ▾] (seleção) + botão "Novo…"
<DataList>           tabela (≥768px) / cards (<768px) + contagem + "Carregar mais"
<ConfirmDialog>      exclusão
<XFormDialog>        criar/editar
```

**Nada fica abaixo do `DataList`.** Com scroll infinito o fim da página nunca chega — botão de criar,
totalizadores e ações de página vivem no `ListToolbar`.

## Geometria do `ListToolbar` — UMA linha, controles à esquerda, ações à direita

```
≥768px   [ busca ][ filtro ][ filtro ][ ordenação ][ Limpar ]          [ ação ][ ação ]
         └─ grupo da esquerda: flex-1 + flex-wrap (quebra controle a controle) ┘ └ ml-auto ┘
640–768  [ busca ]                                                  [ Filtros ][ ação ]
<640     [ busca ─────────────────────────────── ]
         [ Filtros ][ ação ][ ação ]              (flex-wrap; filtros+ordenação no dialog)
```

- **Controles de recorte (busca, filtros, ordenação) moram no canto superior ESQUERDO**, na mesma
  linha das ações. Sem busca, a ordenação sozinha abre a linha à esquerda.
- **Ações à direita** (`sm:ml-auto`), alinhadas no topo (`items-start`) — quando os filtros quebram
  em duas linhas, as ações não descem junto.
- Os controles do desktop ficam num wrapper `hidden md:contents`: cada `Select` vira item do
  `flex-wrap` da linha e quebra sozinho, em vez de o bloco inteiro descer de uma vez.
- Sem busca, o grupo da esquerda é `max-md:hidden` — grupo vazio numa coluna flex deixa o `gap` como
  espaço fantasma acima das ações no celular.
- **Filtro do toolbar é controle de UMA altura (`h-9`), sem `<Label>` empilhado.** A linha é
  `items-center`: o campo rotulado desce meia linha e fica torto. O rótulo visível mora DENTRO do
  controle — `InputGroup` + `InputGroupAddon` (`[De | dd/mm/aaaa]`) para data/texto, valor "Todos os
  status" para `Select` — e o nome acessível vai em `aria-label` contendo o texto visível ("De", não
  "Data inicial": leitor de voz e `getByLabelText` procuram pelo que está na tela). Nada de `id`/`htmlFor`: os filtros
  montam duas vezes (linha + dialog) e o `htmlFor` focaria a cópia escondida.

**PROIBIDO:** filtros/ordenação numa **2ª linha** abaixo das ações · `ml-auto` num controle de
recorte (empurra a ordenação pra direita, embaixo dos botões — a esquerda fica vazia e a tela parece
quebrada) · toolbar ad-hoc (`div` com `Select` + `Button`) ao lado ou em vez do `ListToolbar`.
Mesma regra para barra de filtros **sem lista** (dashboard, relatório): controles agrupados no topo
à esquerda, acima das abas; no celular viram um botão "Filtros" que abre `FormDialog` — troca por
CSS, nunca `useIsMobile()`.

## Invariantes

- **Tabela no desktop vira card no mobile.** UMA definição de coluna produz as duas renderizações.
  Column-collapse (`hidden lg:table-cell`) continua existindo — mas para densidade **acima** de 768px,
  não como substituto do card.
- **Scroll infinito de 10 em 10.** Paginação por número de página está **abolida** — sem exceção.
- **Toda lista tem busca.** Toda lista com coluna de status tem filtro de status.
- **Toda lista tem ordenação** (`makeSortOptions`): mais recentes (default) · mais antigos · A→Z ·
  Z→A · atualizados por último.
- **`q`/`status`/`sort`/`order` moram na URL** (`validateSearch`). A única exceção é o texto em
  digitação, que é buffer de debounce dentro do `SearchInput`.

## `useInfiniteList` — três decisões que parecem erradas e não são

**1. A query key é `[endpoint, "list", "infinite", params]`.** O discriminador vai na posição 2,
*depois* de `"list"`. É o que faz o `invalidateQueries({ queryKey: [endpoint, "list"] })` das mutations
do `useCrud` casar por prefixo. Mover pro índice 1 (`[endpoint, "infinite", …]`) produz uma lista que
**nunca atualiza** depois de criar/excluir — falha silenciosa.

**2. `staleTime: 30_000`, não `0`.** A convenção do `useList` é `staleTime: 0` + `refetchOnMount:
"always"`, e ela existe pra garantir frescor pós-mutation. Mas quem garante isso é a **invalidação**,
que ignora `staleTime`. Com `0`, a navegação lista → detalhe → voltar refaz **todas** as páginas
carregadas, em sequência.

**3. Sem `placeholderData: keepPreviousData`.** Em infinite query isso segura as N páginas do filtro
anterior enquanto a nova página 1 carrega, e depois dá um snap. O `DataList` escurece as linhas atuais.

Mudança de filtro/sort/search **não precisa de reset manual** — está na key, então é outra query, que
começa no `initialPageParam`. Sem `useEffect`, sem ref.

## Invalidação × infinite query (mora no `useCrud`, invisível à tela)

Invalidar uma lista de 12 páginas dispara **12 requests sequenciais** (o TanStack refaz página por
página, re-derivando cada `pageParam`). `maxPages` **não** serve — descarta pela outra ponta e some
com o topo da lista.

| Mutation | Estratégia |
| --- | --- |
| **Delete** | Splice cirúrgico via `setQueriesData` + decrementa `pages[0].total`. **Zero request.** As listas paginadas continuam invalidando de verdade (`predicate: queryKey[2] !== "infinite"`) |
| **Create** | Trunca pra 1 página **antes** de invalidar (12 requests → 1). Sob o sort padrão `created_at DESC` a linha nova pertence ao topo de qualquer jeito |
| **Update** | Substitui no lugar + `refetchType: "none"`. Se a edição fez a linha deixar de casar o filtro, ela some no próximo mount — trade deliberado |

## `DataList` — roles de coluna

| `role` | Onde aparece no card |
| --- | --- |
| `primary` | Título (exatamente uma coluna). Renderize um `<Link>` de verdade aqui |
| `secondary` | Subtítulo muted abaixo do título |
| `badge` | Chip no canto superior direito (status) |
| `meta` *(default)* | Linha "rótulo \| valor" no corpo |
| `hidden` | Só desktop (coluna larga, notas) |

`renderCard` por coluna encurta uma célula larga; `renderCard` no componente ignora os roles e desenha
o card inteiro.

## `variant` — quando a tabela não é o container certo

| `variant` | Container | Quando |
| --- | --- | --- |
| `"table"` *(default)* | tabela ≥768px, card abaixo | Coleção **textual**. É o caso de quase toda tela |
| `"grid"` | card em grade 1→2→3 colunas, todos os breakpoints | O conteúdo **é visual** (veículo com foto, pedido com miniatura) — espremer a imagem numa célula desperdiça exatamente o que se veio ver |
| `"stack"` | card full-width empilhado, todos os breakpoints | O item **expande no lugar** (fila de aprovação com documentos, log com payload): não cabe numa linha de tabela nem numa coluna de grade |

`columns` continua sendo a fonte dos roles do card nos três — o `variant` só troca o container. Numa
coleção textual, sair do default é regressão: a tabela é mais densa e mais escaneável no desktop.

### Quatro decisões estruturais

- **O switch desktop/mobile é CSS**, não `useIsMobile()`. O hook resolve em `useEffect` e devolve
  `undefined` no primeiro render → tabela pisca no celular, e a subárvore inteira remonta a cada resize
  cruzando 768px, derrubando o `IntersectionObserver` junto. Custo do CSS: as duas árvores no DOM e
  `cell(item)` chamado duas vezes. Em 10–200 linhas carregadas, irrelevante.
- **Permissão fica no caller** — `actions={[...(can(P.UPDATE) ? [edit] : [])]}`. Os 5 projetos têm
  hooks de permissão diferentes; o componente vendorado não pode acoplar na auth de nenhum.
- **Click na linha é conveniência; a coluna `primary` renderiza um `<Link>`.** Mantém o componente
  agnóstico de rota (5 route trees), preserva middle-click / copiar link, e dá alvo focável real.
- **Card é `<div>`, NUNCA `<a>`.** Envolver o card inteiro numa âncora aninha os `<button>` de ação
  dentro dela — HTML inválido, quebra no Safari.

## `StaticDataList` — a tabela BOUNDED (mesmo arquivo, mesmo contrato de coluna)

Nem toda tabela é coleção. Itens de um orçamento, parcelas de um título, ranking de mecânicos do mês,
versões de um agente, linhas de um inventário fechado: o conjunto **já veio inteiro** e o domínio limita
o tamanho. Essas não têm busca, nem filtro, nem `skip`/`limit` — mas continuam precisando virar **card
no mobile**, porque a regra é da tabela, não da paginação.

```tsx
<StaticDataList
  items={quote.items}
  columns={ITEM_COLUMNS}
  getRowId={(item) => item.id}
  emptyTitle="Nenhum item neste orçamento."
  tableFooter={<TableFooter>…</TableFooter>}   {/* linha de totais — só desktop */}
/>
```

Difere do `DataList` só no que sobra: sem `isFetching`/`hasNextPage`/`fetchNextPage`/`total`, sem
sentinela, sem "Carregar mais", sem contagem, sem `onClearFilters`. Ganha `tableFooter` (o
`<TableFooter>` de totais; o card mobile **não** tem equivalente — o total do mobile é do caller) e
`isLoading` opcional.

**Escolha errada é regressão nos dois sentidos:** usar `StaticDataList` numa coleção que cresce com o
uso é fetch-all disfarçado; usar `DataList` numa tabela de 6 itens de orçamento paga sentinela,
contagem e "Carregar mais" que nunca fazem sentido. O teste é uma pergunta só — **o número de linhas
cresce com o uso do sistema?** Sim → `DataList` + `useInfiniteList`. Não → `StaticDataList`.

## Filtro de status com contagem

Quando o status é o recorte principal da tela (estoque, funil), o `Select` de status diz **quantos
registros há em cada opção**, agrupado por etapa:

```
Todos os veículos · 212
── Em negociação ──────────        SelectGroup + SelectLabel por etapa; a 1ª opção do grupo
   Toda a negociação · 43          é a etapa inteira, depois os status dela
   Em avaliação · 12
── Estoque ────────────────
   Todo o estoque · 169
   Em estoque · 150
── Outros ─────────────────        status fora de etapa: só aparece com registro (ou selecionado)
```

- **Um controle só.** Abas por etapa + filtro de status em cima são dois recortes do mesmo eixo que se
  contradizem (aba "Estoque" com filtro "Em avaliação" = lista vazia sem motivo aparente).
- **Backend:** `GET …/{recurso}/status-counts?search=`, declarado ANTES de `/{id}`, mesma permissão de
  leitura da lista: `SELECT status, COUNT(*) {PREDICADO} GROUP BY status` reaproveitando o predicado
  `Final` da listagem com o filtro de status **nulo** — a contagem respeita a busca, não o próprio
  status (senão toda opção fora da escolhida marcaria 0).
- **Resposta é lista `[{status, total}]`, nunca dict com o status como chave:** o `ApiClient`
  camelcaseia chave de dict (`nova_proposta` chega como `novaProposta` e a contagem some).
- **Query key sob o prefixo da lista** (`[endpoint, "status-counts", { search }]`): toda invalidação
  de mutation já refresca a contagem. `keepPreviousData` para o número não piscar entre buscas.
- Totais de etapa e "Todos" somados no cliente a partir do mapa etapa→status (fonte única em
  `types/`). **O número some enquanto carrega** — nunca um `0` falso.
- Na URL, `stage` e `status` são exclusivos: `validateSearch` descarta `stage` quando há `status`.

## Seleção múltipla — menu `Ações` no slot de ações

Ação em lote (publicar, arquivar, exportar os marcados) é um `DropdownMenu` **"Ações" com badge da
contagem** no slot `actions` do `ListToolbar`, antes do "Novo…" (`BulkActionsMenu`). O estado mora
na TELA (`useListSelection`); o `DataList` só desenha o checkbox (`selection={{ selectedIds,
onToggle }}`, no canto do card).

```
[ busca ][ Todo o estoque · 169 ][ ordenação ]         [ Ações 3 ▾ ][ Importar ][ Novo ]
                                                        │ 3 selecionados
                                                        │ Selecionar os 24 desta página
                                                        │ Limpar seleção
                                                        │ ─────────────
                                                        │ Publicar nos portais  2 em estoque
```

- **NUNCA barra de seleção solta entre o toolbar e a lista** — empurra a grade, some no scroll e não
  cabe a segunda ação.
- **A seleção guarda o ITEM, não só o id:** atravessa página/scroll, e a ação precisa do rótulo de
  quem já saiu da tela.
- **"Selecionar os N desta página"** (paginado) / **"os N carregados"** (scroll infinito,
  `scopeLabel`) — nunca "Selecionar todos" marcando só o visível: o usuário publica 24 de 169 achando
  que foi tudo.
- **Cada ação declara a elegibilidade.** A seleção vale para a lista toda; a ação filtra os marcados
  que ela alcança, mostra o alcance no item ("2 em estoque"), fica `disabled` com 0, e o dialog dela
  diz quantos ficaram de fora.
- **Limpar DENTRO dos handlers** de busca/filtro/ordenação, nunca num `useEffect` — um render depois,
  o menu ainda ofereceria ação sobre item que o filtro já tirou da tela. Trocar de página não limpa.
- Ação nova = um `DropdownMenuItem` a mais como `children`. Sem permissão para nenhuma ação em lote →
  sem menu e sem checkbox.

## Sentinela de scroll infinito

Deps **vazias** + ref-espelho do estado. `observe()` dispara o callback com o alvo ainda visível, então
qualquer dep que muda por render recria o observer e re-dispara — passar o objeto `query` como dep é o
erro clássico (referência nova a cada render). `rootMargin: "400px 0px"` ≈ 4 cards.

**Um sentinel só, FORA das duas árvores responsivas** — nó dentro de `display:none` nunca intersecta,
então um sentinel por árvore morreria silenciosamente num dos breakpoints.

A chain-load (sentinel ainda visível depois de carregar) é **correta** — carrega até encher a viewport.
Ela só vira loop infinito se o servidor mentir no `has_more`; é por isso que a sentinela `LIMIT+1` do
backend precisa ser exata, e não uma estimativa.

## Acessibilidade

- O `<Button>Carregar mais</Button>` é o mecanismo **primário**, sempre renderizado quando há próxima
  página. O `IntersectionObserver` é progressive enhancement que o aperta. É também o fallback quando
  o container não rola (viewport curta, usuário com zoom).
- `aria-live="polite"` na contagem ("40 de 128"), `aria-busy` no container.
- **Não** usar `role="feed"` — é especificado pra stream de artigos e conflita com semântica de
  `<table>`.

## F5 e voltar do browser

A URL carrega `q/sort/order` — **não** quantas páginas foram carregadas, de propósito.

- **Voltar (lista → detalhe → voltar):** o cache do TanStack ainda tem as N páginas → restaura
  completo, de graça. (É o `staleTime: 30_000` que evita o refetch de todas elas.)
- **F5 no meio do scroll:** volta pra página 1. Aceito: scroll infinito é session-scoped, e quem dá F5
  na página 12 quer um registro específico — a busca serve isso melhor que replay de 12 fetches.

Persistir `?pages=12` produziria uma URL que mente assim que o dado muda, 12 requests sequenciais no
load, e um param que ninguém compartilharia.

## Paginação por número de página: abolida

"Pular pra página N" só faz sentido se N for endereço estável — com dado mutável não é. A necessidade
real é *achar um registro* (busca + filtro + sort) ou *saber quantos são* (o `total` exato no
cabeçalho, que o backend preserva calculando o COUNT em `skip == 0`).

Único caso que merece ser nomeado e recusado: export/auditoria que enumera tudo. Isso é **endpoint de
export** (CSV/PDF streamado), não tela de lista.

## `EntityPicker` não muda

O picker tem mecânica própria — cresce o `limit` de 10 em 10 sempre com `skip=0`, e cada degrau é uma
entrada de cache. O contrato "`total` exato quando `skip == 0`" existe justamente pra ele continuar
funcionando sem alteração. Ver `entity-picker.md`.

## Receita (before/after em `entity`)

```tsx
const SORT_OPTIONS = makeSortOptions({ alphaKey: "name", alphaLabel: "Nome" });

export const Route = createFileRoute("/…/clientes/")({
  validateSearch: (s: Record<string, unknown>): CustomersSearch => ({
    q: typeof s.q === "string" && s.q ? s.q : undefined,
    sort: SORT_OPTIONS.some((o) => o.sort === s.sort) ? (s.sort as string) : undefined,
    order: s.order === "asc" ? "asc" : s.order === "desc" ? "desc" : undefined,
  }),
  component: CustomersPage,
});

function CustomersPage() {
  const { q, sort, order } = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const list = useInfiniteList<Customer>(endpoint, { search: q, sort, order });

  const columns = useMemo<DataListColumn<Customer>[]>(() => [
    { id: "name", header: "Nome", role: "primary",
      cell: (c) => <Link to="…" params={{ … }} className="font-medium hover:underline">{c.name}</Link> },
    { id: "company", header: "Empresa", role: "secondary",
      className: "hidden xl:table-cell", cell: (c) => c.company ?? "—" },
    { id: "document", header: "Documento", className: "hidden sm:table-cell", cell: formatDocument },
  ], [orgId]);

  const setSearch = useCallback(
    (next: string | undefined) => navigate({ search: (p) => ({ ...p, q: next }), replace: true }),
    [navigate]
  );

  return (
    <div className="space-y-4">
      <ListToolbar
        search={q} onSearchChange={setSearch} searchPlaceholder="Buscar por nome, documento…"
        sort={sort} order={order} sortOptions={SORT_OPTIONS}
        onSortChange={(s, o) => navigate({ search: (p) => ({ ...p, sort: s, order: o }) })}
        actions={can(P.CREATE) && <Button onClick={openCreate}>Novo cliente</Button>}
      />
      <DataList
        {...list}
        columns={columns} actions={actions} getRowId={(c) => c.id}
        onRowClick={(c) => navigate({ to: "…", params: { … } })}
        isFiltered={!!q}
        emptyTitle={q ? "Nenhum cliente encontrado." : "Nenhum cliente cadastrado."}
        onClearFilters={() => setSearch(undefined)}
        countLabel={(n) => `${n} cliente${n === 1 ? "" : "s"}`}
      />
      {/* dialogs */}
    </div>
  );
}
```

Some da tela anterior: `PAGE_SIZE`, o param `page`, a aritmética de `lastPage`, o bloco Prev/Next, o
`<Table>` inteiro, as `TableRow` de loading/empty e o `<Input>` de busca inline. ~250 → ~110 linhas.

## Don'ts

- **NUNCA** `useState` pra filtro, busca commitada, sort ou página — é URL (`validateSearch`).
- **NUNCA** passar o objeto `query` nas deps do effect do `IntersectionObserver`.
- **NUNCA** `<Table>` sem alternativa em card abaixo de 768px.
- **NUNCA** paginação por número de página numa tela nova.
- **NUNCA** `fetch-all` com `limit: 500` "porque a tabela é pequena" — ela não vai continuar pequena.
- **NUNCA** colocar botão de criar (ou qualquer ação) abaixo da lista.
- **NUNCA** barra de seleção/ação em lote entre o toolbar e a lista — é o menu `Ações` no toolbar.
- **NUNCA** abas por etapa + filtro de status juntos — é um `Select` agrupado, com contagem.
- **NUNCA** sort key que não esteja no whitelist do backend, nem coluna nullable como sort key.
