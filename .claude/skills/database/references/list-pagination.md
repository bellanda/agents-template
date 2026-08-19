# Listagem paginada — sentinela, ordenação e índices

> Reference do gate `database` (item 4 do checklist). Contrato de TODO endpoint de lista.
> Contraparte de frontend: gate `frontend` → `references/list-screen.md`.

## As 4 regras

1. **NUNCA `COUNT(*) OVER()` em query de lista.** O `WindowAgg` tem `PARTITION BY` vazio, então a
   partição é o result set inteiro e ele precisa consumir **todas** as linhas filtradas antes de emitir
   a primeira — o `Limit` não desce abaixo dele. Custo O(linhas do filtro) **por página**, com heap
   fetch por linha se for `SELECT *`. Com scroll infinito de 10 em 10 isso é patológico.
2. **Sentinela `LIMIT limit + 1`.** Veio `limit+1` linha? `has_more = true`, descarta a extra. Exato,
   custa uma linha.
3. **`total` só quando `skip == 0`**, via `COUNT(*)` separado. Fora daí devolve o lower bound
   `skip + len(items) + has_more`. O `EntityPicker` sempre manda `skip=0`, então o `hasMore =
   items.length < total` dele continua exato; o `useInfiniteList` sempre busca a página 0 primeiro,
   então `pages[0].total` é o número que vai pro cabeçalho.
4. **Todo `ORDER BY` termina com desempate por `id`.** Ver abaixo — não é preciosismo.

## Por que o desempate é obrigatório

SQL garante que linhas com a mesma chave de ordenação apareçam **contíguas**, não em que ordem entre
si. Postgres devolve ordens diferentes entre execuções quando o plano muda (index scan vs seq+Sort),
quando entra paralelismo, ou depois de HOT update/autovacuum reordenar tuplas no heap.

Com OFFSET isso não é teórico:

- Página 1 (`LIMIT 10 OFFSET 0`): o empate resolve `A, B, C`. A cai na posição 10 e é exibida.
- Página 2 (`LIMIT 10 OFFSET 10`) — **execução separada**. O empate resolve `B, A, C`. A posição 10 é
  B agora; a 11 é A.
- Página 2 devolve `A, C, …`. **A aparece duas vezes; B nunca aparece.**

Paginação por número de página escondia isso (a duplicata caía noutra tela). Scroll infinito põe as
duas cópias no mesmo array achatado → `Warning: Encountered two children with the same key` e linha
repetida visível.

E empate é a **regra**, não a exceção: `created_at timestamptz DEFAULT now()` e `now()` é
*transaction-stable* — importar 500 clientes numa transação gera 500 `created_at` byte-idênticos,
exatamente sob a ordenação default. `ORDER BY status` empata aos milhares por construção.

`id` sendo `uuidv7()` é único **e** time-ordered, então o desempate tem significado (ordem de inserção
dentro do empate), não é arbitrário. **A direção do desempate acompanha a direção principal.**

## Whitelist de ORDER BY (a coluna não pode ser bind param)

asyncpg não tem helper de quoting de identificador (não existe equivalente ao
`psycopg.sql.Identifier`). Então a string do cliente é **só chave de dict** — o fragmento SQL é
literal, escrito à mão no fonte.

```python
# backend/src/api/repositories/shared/sorting.py
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class SortSpec:
    """Os dois fragmentos de uma chave, mais qual vale sem `order` explícito."""

    asc: str
    desc: str
    default_order: str = "asc"


SortMap = Mapping[str, SortSpec]

DEFAULT_SORT_KEY: Final = "created_at"


def by_column(column: str, *, alias: str = "", default_order: str = "asc") -> SortSpec:
    """Monta os dois fragmentos de `column`, SEMPRE desempatados por `id`.

    `column`/`alias` são literais que o repository escreve — o request só escolhe uma
    *chave* do mapa resultante, nunca a coluna. `alias` é obrigatório quando a query tem
    JOIN: `created_at`/`id` existem nos dois lados da maioria deles.
    """
    prefix = f"{alias}." if alias else ""
    return SortSpec(
        asc=f"{prefix}{column} ASC, {prefix}id ASC",
        desc=f"{prefix}{column} DESC, {prefix}id DESC",
        default_order=default_order,
    )


def standard_sorts(
    alias: str = "",
    *,
    alpha: str | None = None,
    updated: bool = True,
    extra: Mapping[str, SortSpec] | None = None,
) -> dict[str, SortSpec]:
    """O mapa canônico: `created_at` (default, mais novo primeiro), chave alfabética, `updated_at`."""
    sorts = {"created_at": by_column("created_at", alias=alias, default_order="desc")}
    if alpha:
        sorts[alpha] = by_column(alpha, alias=alias)
    if updated:
        sorts["updated_at"] = by_column("updated_at", alias=alias, default_order="desc")
    if extra:
        sorts.update(extra)
    return sorts


def order_by(
    sorts: SortMap,
    sort: str | None,
    order: str | None,
    default: str = DEFAULT_SORT_KEY,
) -> str:
    """Resolve o par do request num fragmento. Chave desconhecida → `sorts[default]`."""
    # Fallback, NÃO 422 — bookmark velho ou constante desatualizada no front não pode
    # branquear a tela.
    spec = sorts.get(sort or "") or sorts[default]
    direction = (order or spec.default_order).lower()
    return spec.desc if direction == "desc" else spec.asc
```

Um `SortMap` de repository vira **uma linha**, e o `default` sai como argumento de `order_by` quando
não é `created_at`:

```python
_SORTS: Final[SortMap] = standard_sorts(alpha="name")                    # customers
_SORTS: Final[SortMap] = standard_sorts("v", alpha="plate")              # vehicles (join)
_SORTS: Final[SortMap] = standard_sorts("m", updated=False)              # stock_movements
_SORTS: Final[SortMap] = standard_sorts(                                 # accounts_payable
    "p", alpha="number", extra={"issue_date": by_column("issue_date", alias="p", default_order="desc")}
)
order = order_by(_SORTS, params.sort, params.order, default="issue_date")
```

**`default_order` por chave, não global.** `created_at`/`updated_at`/datas de documento vão `desc`
sem `?order=` (a tela promete "mais recentes primeiro"); chave alfabética vai `asc`. Sem isso a
primeira renderização de uma tela ordenada por nome chega invertida.

**Só coluna `NOT NULL` entra no whitelist.** `ASC` default é `NULLS LAST`, `DESC` default é
`NULLS FIRST` — então `ORDER BY updated_at DESC` numa coluna nullable lidera com as linhas que nunca
foram atualizadas, o oposto da promessa da tela. E fazer `DESC NULLS LAST` casar com índice exige um
**segundo** índice (btree lido de trás pra frente inverte também a posição dos nulls). Uma regra
elimina os dois problemas. Em `vehicles` a chave alfabética é `plate` (NOT NULL), não `brand`.

## Repository canônico

O predicado é compartilhado entre a query de página e a de count — senão eles divergem. Vive numa
constante `Final` de módulo:

```python
# `FROM` + `WHERE` juntos na constante: o `COUNT` reusa o bloco inteiro, então nem a
# tabela nem o JOIN podem divergir entre as duas queries.
# $1 = org_id, $2 = search. Paginação ($3/$4) vem DEPOIS — invariante: o predicado
# ocupa os menores números, LIMIT/OFFSET no fim, senão a query de COUNT (que só
# recebe $1/$2) não casa.
_LIST_FILTER: Final = """
    FROM customers
    WHERE organization_id = $1
      AND deleted_at IS NULL
      AND (
            $2::text IS NULL
            OR name ILIKE '%' || $2 || '%'
            OR document ILIKE '%' || $2 || '%'
            OR phone ILIKE '%' || $2 || '%'
      )
"""

_SORTS: Final[SortMap] = standard_sorts(alpha="name")


class CustomerRepository:
    async def list_by_org(self, conn: Connection, org_id: UUID, params: ListParams) -> ListPage:
        order = order_by(_SORTS, params.sort, params.order)
        rows = await conn.fetch(
            # Interpolação SÓ de constante `Final` deste módulo e de fragmento vindo
            # de whitelist fechado. Todo VALOR continua em $n. Ver carve-out abaixo.
            f"SELECT * {_LIST_FILTER} ORDER BY {order} LIMIT $3 OFFSET $4",
            org_id,
            params.search,
            params.fetch_limit,  # sentinela: a 11ª linha só existe pra responder has_more
            params.skip,
        )
        total = None
        if params.wants_total:  # só a primeira página paga o COUNT
            total = await conn.fetchval(
                f"SELECT COUNT(*) {_LIST_FILTER}",
                org_id,
                params.search,
            )
        return sentinel(rows, params, total)
```

### Carve-out do "NUNCA f-string em SQL"

A regra existe pra impedir **injection** — valor vindo do usuário concatenado no SQL. Interpolar
(a) constante `Final` de módulo e (b) fragmento de `ORDER BY` vindo de whitelist fechado não é
injection: nenhum dos dois contém dado de request. **Todo valor continua em `$n`.**

Qualquer outra f-string em SQL segue proibida. Um teste trava isso — e ele **importa os módulos e
anda nos `_SORTS` de verdade**, não faz grep no fonte: os fragmentos são construídos por
`by_column`, então nenhuma regex sobre o texto do arquivo veria a string final.

```python
ORDER_BY = re.compile(
    r"^[a-z_]+(\.[a-z_]+)? (ASC|DESC)( NULLS (FIRST|LAST))?"
    r"(, [a-z_]+(\.[a-z_]+)? (ASC|DESC)( NULLS (FIRST|LAST))?)*$"
)


def iter_sort_maps() -> Iterator[tuple[str, SortMap]]:
    """Todo `_SORTS` de todo `*_repository.py` — o teste descobre sozinho os novos."""
    root = Path(api.repositories.__file__).parent
    for path in sorted(root.rglob("*_repository.py")):
        name = f"api.repositories.{path.relative_to(root).with_suffix('').as_posix().replace('/', '.')}"
        sorts = getattr(importlib.import_module(name), "_SORTS", None)
        if sorts is not None:
            yield name, sorts


def test_every_sort_fragment_is_a_literal_order_by():
    seen = 0
    for name, sorts in iter_sort_maps():
        seen += 1
        for key, spec in sorts.items():
            assert spec.default_order in ("asc", "desc"), f"{name}.{key}"
            for fragment in (spec.asc, spec.desc):
                assert ORDER_BY.fullmatch(fragment), f"{name}.{key}: {fragment!r}"
                assert fragment.rstrip().endswith((" id ASC", " id DESC")), (
                    f"{name}.{key} sem desempate por id"
                )
    assert seen, "nenhum _SORTS encontrado — o teste parou de cobrir alguma coisa"
```

A asserção do desempate é o que impede ele de ser esquecido em qualquer `SortMap` futuro; a
asserção final de `seen` é o que impede o teste de virar no-op silencioso se o layout de
diretórios mudar.

## Helpers compartilhados

```python
# backend/src/api/repositories/shared/listing.py
@dataclass(frozen=True, slots=True)
class ListParams:
    skip: int = 0
    limit: int = 10
    search: str | None = None
    sort: str | None = None
    order: Literal["asc", "desc"] | None = None

    @property
    def fetch_limit(self) -> int:
        """O que entra em ``LIMIT $n`` — um a mais que o pedido, a linha sentinela."""
        return self.limit + 1

    @property
    def wants_total(self) -> bool:
        """Só a primeira página paga o ``COUNT(*)``."""
        return self.skip == 0


@dataclass(frozen=True, slots=True)
class ListPage:
    items: list[dict]
    total: int
    has_more: bool


def sentinel(rows: Sequence[Any], params: ListParams, total: int | None = None) -> ListPage:
    """Fatia um resultado over-fetched (``LIMIT limit + 1``) no envelope."""
    has_more = len(rows) > params.limit
    items = [dict(row) for row in rows[: params.limit]]
    if total is None:
        total = params.skip + len(items) + int(has_more)
    return ListPage(items=items, total=total, has_more=has_more)
```

`ListParams` mora em `listing.py` (camada de repository) e não em `list_params.py` — o repository
não pode importar de `routes/`. O módulo de rotas só constrói o objeto.

```python
# backend/src/api/routes/shared/list_params.py
DEFAULT_PAGE_LIMIT: Final = 10
MAX_PAGE_LIMIT: Final = 200
MIN_SEARCH_LENGTH: Final = 3
# Teto do termo de busca. Um endpoint de listagem pode ser anônimo (mural público), e um
# ILIKE '%…%' com termo gigante é trabalho gratuito para quem manda a request. 120 chars
# cobrem qualquer caixa de busca real.
MAX_SEARCH_LENGTH: Final = 120


async def get_list_params(
    skip: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    search: str | None = Query(None, max_length=MAX_SEARCH_LENGTH),
    sort: str | None = Query(None, max_length=40),
    # Sem default: `order` ausente cai no `default_order` da chave escolhida (`desc`
    # para datas, `asc` para alfabética). Fixar "desc" aqui inverteria toda tela
    # ordenada por nome na primeira renderização.
    order: Literal["asc", "desc"] | None = Query(None),
) -> ListParams:
    term = (search or "").strip()
    return ListParams(
        skip=skip,
        limit=limit,
        # < 3 chars vira scan da org inteira a cada tecla, e não produz trigrama
        # utilizável se um GIN pg_trgm entrar depois. Trata como "sem busca".
        search=term if len(term) >= MIN_SEARCH_LENGTH else None,
        sort=sort,
        order=order,
    )


ListParamsDep = Annotated[ListParams, Depends(get_list_params)]
```

O `DEFAULT_PAGE_LIMIT`/`MAX_PAGE_LIMIT` vivem **só aqui** — constante de limite duplicada em route
file é a forma como um endpoint volta silenciosamente pra `limit=100`. `rg -n "MAX_PAGE_LIMIT|PAGE_SIZE"
src/api/routes` deve casar um arquivo só.

## Envelope

```python
class PagedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int    # exato quando skip == 0; lower bound depois
    skip: int
    limit: int    # o PEDIDO, nunca o +1 da sentinela
    has_more: bool = False   # default=False permite migrar rota a rota
```

Ecoar `limit+1` faz a aritmética de `skip` do cliente derivar em 1 por página. Não faça.

## Índices

**Um índice serve as duas direções** (scan reverso), e o `SortMap` nunca emite direções mistas — então
uma chave de sort custa **um** índice, não dois.

**Um índice por tabela: só a chave DEFAULT.** É ela que toda página de scroll infinito usa. As
chaves não-default (alfabética, `updated_at`) caem em **Incremental Sort** sobre os índices
`(org, coluna)` que já existem — medido em 200k linhas: 0,08 ms. Criar índice pra elas é gastar
escrita em combinação rara. Medido no checkpoint (200k linhas, 67k na org alvo):

| query | sem índice | com o composto |
| --- | --- | --- |
| página `skip=0` | 22,9 ms · 8114 buffers · Parallel Seq Scan + top-N heapsort | **0,07 ms · 5 buffers** · Index Scan |
| página `skip=100` | 18,2 ms · 8114 buffers | **0,06 ms · 10 buffers** |
| `COUNT(*)` (só em `skip=0`) | 19,9 ms · Bitmap Heap Scan | **7,7 ms** · Index Only Scan, `Heap Fetches: 0` |
| `COUNT(*) OVER()` (o padrão antigo) | 76,6 ms + **9,4 MB de spill em disco por página** | eliminado |

### `CONCURRENTLY` só cabe UMA por arquivo — regra do dbmate, verificada

O dbmate manda o bloco `up` inteiro como **uma** string multi-statement, e o `lib/pq` usa o *simple
query protocol*, que o Postgres embrulha numa transação implícita. Resultado: a **segunda**
`CREATE INDEX CONCURRENTLY` do arquivo morre com `25001: CREATE INDEX CONCURRENTLY cannot run
inside a transaction block` — **mesmo declarando `transaction:false`** (o dbmate ainda loga
"Applied" antes de estourar, então é fácil ler errado). Verificado contra o dbmate 2.33.

Duas saídas, escolha pela volumetria:

- **Tabela grande / tráfego real** → **um índice por arquivo de migration**, cada um com
  `-- migrate:up transaction:false` e uma única statement. É o preço do build sem lock de escrita.
- **Tabela ainda pequena** (early-stage: build sub-segundo) → **uma migration transacional** com
  `CREATE INDEX` normal para todos os índices. Comente no arquivo por que não é `CONCURRENTLY` e
  deixe o caminho de saída escrito, senão alguém "corrige" para `CONCURRENTLY` e quebra o deploy.

```sql
-- Um índice por arquivo — a forma que roda sem lock de escrita.
-- migrate:up transaction:false
CREATE INDEX CONCURRENTLY ix_customers_org_created_at
  ON public.customers USING btree (organization_id, created_at DESC, id DESC)
  WHERE (deleted_at IS NULL);

-- migrate:down transaction:false
DROP INDEX CONCURRENTLY IF EXISTS public.ix_customers_org_created_at;
```

```sql
-- Vários índices de uma vez — só enquanto o build é sub-segundo.
-- migrate:up
CREATE INDEX IF NOT EXISTS ix_customers_org_created_at
  ON public.customers USING btree (organization_id, created_at DESC, id DESC)
  WHERE (deleted_at IS NULL);

CREATE INDEX IF NOT EXISTS ix_vehicles_org_created_at
  ON public.vehicles USING btree (organization_id, created_at DESC, id DESC)
  WHERE (deleted_at IS NULL);

-- migrate:down
DROP INDEX IF EXISTS public.ix_vehicles_org_created_at;
DROP INDEX IF EXISTS public.ix_customers_org_created_at;
```

**Filtro × sort é produto cartesiano — não gere todas as combinações.** Um composto precisa liderar
com as colunas de igualdade: `(org, status, created_at DESC, id DESC)` serve a lista filtrada por
status, mas a query "todos os status" não usa esse índice pra ordenar. Regra: `(org, <sort default>, id)`
em toda tabela de lista, e `(org, status, <sort default>, id)` **só** nas 2–3 tabelas em que filtrar
por status é o acesso dominante. Sort fora do default sob filtro de status cai em Incremental Sort —
aceitável, combinação rara.

**O predicado parcial do índice tem que casar o do `WHERE`.** Tabela com soft delete leva
`WHERE (deleted_at IS NULL)`; razão contábil que nunca apaga (movimento de estoque, sessão de caixa)
leva índice **sem** predicado — um `WHERE deleted_at IS NULL` num índice de tabela sem a coluna é
erro de migration, e num índice de tabela que tem a coluna mas cuja query não filtra por ela o
planner simplesmente ignora o índice.

O desempate **não** precisa estar no índice pra correção (a correção vem do `ORDER BY`); ele evita um
nó `Sort`. Com `(org, name)` e `ORDER BY name, id`, o PG13+ usa **Incremental Sort** — lê o índice na
ordem de `name` e ordena só dentro de cada grupo de `name` igual. Adicione `id` ao índice apenas na
chave default das tabelas de maior tráfego.

## OFFSET é aceitável aqui — e onde deixa de ser

`OFFSET N` percorre N entradas de índice (mais N heap fetches se for `SELECT *`), linear em N. Mas
**N é a profundidade de scroll, não o tamanho da coleção.** Comparado com o que existia:

| | tuplas tocadas (org de 5.000 linhas, 5 páginas) |
| --- | --- |
| `COUNT(*) OVER()` a 20/página, 3 fetches | 3 × 5.000 = **15.000 linhas de heap** |
| Porte ingênuo pra 10/página, 5 fetches | 5 × 5.000 = **25.000** |
| Este contrato | 5.000 (count, uma vez) + walk de `0+10+20+30+40` + **55 linhas de heap** |

OFFSET começa a doer por volta de **50.000** — que a 10/página exigiria 5.000 fetches sequenciais numa
sessão. Não acontece.

**Keyset/cursor foi avaliado e recusado**: com sort por coluna arbitrária são 3 chaves × 2 direções =
6 predicados de comparação de linha, cada um com tratamento de tipo próprio; coluna nullable não aceita
`ROW(a,b) > ROW($1,$2)` de jeito nenhum (comparação com NULL dá NULL), exigindo bloco null + flag no
cursor e um `OR` que o planner frequentemente recusa transformar em range scan — 12 ramos por entidade.
E keyset não dá `total`, que o `EntityPicker` precisa. Reavaliar só se um tenant passar de ~10⁶ linhas
numa lista **e** rolar fundo nela; se só o primeiro for verdade, a resposta é outra UI, não outro cursor.

## Checklist de verificação (rodar antes de replicar o padrão)

```sql
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM customers WHERE … ORDER BY … LIMIT 11 OFFSET 0;
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM customers WHERE … ORDER BY … LIMIT 11 OFFSET 100;
EXPLAIN (ANALYZE, BUFFERS) SELECT COUNT(*) FROM customers WHERE …;
```

- O count deve dar **`Index Only Scan`** com `Heap Fetches:` baixo. Alto = visibility map desatualizado
  → `VACUUM`.
- A query ordenada por chave alfabética com empate deve dar **`Incremental Sort`**, não `Sort` completo.
- Nenhum plano pode conter `WindowAgg`.

## Don'ts

- **NUNCA** `COUNT(*) OVER()` em lista.
- **NUNCA** `ORDER BY` sem desempate por coluna única.
- **NUNCA** sort key nullable no whitelist.
- **NUNCA** 422 em sort key desconhecida — cai no default.
- **NUNCA** ecoar `limit + 1` no envelope.
- **NUNCA** `response_model=list[...]` num endpoint de coleção — é `PagedResponse[T]`.
- **NUNCA** `total=len(items)` — ou é o COUNT real (skip 0) ou é o lower bound do `sentinel()`.
- **NUNCA** endpoint de coleção sem `LIMIT`.
- **NUNCA** duas `CREATE INDEX CONCURRENTLY` no mesmo arquivo dbmate — falha com `25001` mesmo com
  `transaction:false` (um índice por arquivo, ou `CREATE INDEX` normal numa migration transacional).
- **NUNCA** `DEFAULT_PAGE_LIMIT`/`PAGE_SIZE` duplicado em route file — a constante mora em
  `routes/shared/list_params.py` e em nenhum outro lugar.
