# EntityPicker — FK pesquisável + quick-create "Novo…"

> Reference do gate `frontend` (item 8d do checklist). Abra ANTES de colocar qualquer campo de FK
> em um form (selecionar cliente, veículo, fornecedor, contato, organização…). Fonte canônica do
> componente: `references/entity-picker.tsx` (vendored por projeto em
> `components/ui/entity-picker.tsx`, cópia byte-idêntica — depende de `command.tsx`/`popover.tsx`
> shadcn, `cmdk` e `react-icons/lu`).

**Princípio:** campo de FK nunca é `Select` estático nem `Input` de ID cru. É um combobox
**pesquisável no servidor** (clica → digita → a primeira página de 10 vem do backend, rola pra
puxar mais de 10 em 10) com CTA **"Novo…"** que abre o `*FormDialog` da entidade por cima e
**auto-seleciona** o registro criado — o usuário nunca sai do form para cadastrar a dependência.

## Tabela de decisão

| Cenário                                                                    | Use                                        |
| -------------------------------------------------------------------------- | ------------------------------------------ |
| FK cuja lista pode passar de ~20 itens OU cresce por transação/uso         | **EntityPicker** (cliente, veículo, peça…) |
| FK criável no fluxo (faz sentido cadastrar ali: cliente, contato, fornecedor) | EntityPicker **com** quick-create          |
| FK não-criável no fluxo (org no admin, imóvel de inventário externo)       | EntityPicker **sem** `createLabel`/`onCreateNew` (CTA some) |
| Lista bounded administrativa que muda devagar (membros da org, roles, enums) | `Select` residual — não migre              |
| Seletor de CONTEXTO global (trocar org/cliente ativo no header/sidebar)    | `DropdownMenu` — não é campo de form       |

**Critério objetivo:** migre para EntityPicker quando (a) a lista não tem teto natural conhecido
OU (b) cresce a cada operação de negócio. Headcount/enum = Select. **Input de ID/UUID cru =
PROIBIDO** em qualquer caso.

## Anatomia (3 peças)

1. **`EntityPicker<T>` genérico** (`ui/entity-picker.tsx`, canônico) — Popover + Command com
   `shouldFilter={false}` (o servidor decide o recorte; o vazio é `items.length === 0`, nunca o
   auto-hide do `CommandEmpty`, senão o CTA "Novo…" sumiria junto). Busca a cada keystroke via
   `useList({ search, limit }, { enabled: open })` — a query só liga com o popover aberto;
   TanStack Query deduplica/cancela (sem debounce manual). O `limit` começa em **10** (`PAGE_SIZE`)
   e sobe de 10 em 10 quando a lista rola até o fim (`hasMore = items.length < total`): como o
   `limit` entra na query key, cada degrau é uma entrada de cache e o TanStack serve a janela
   anterior enquanto busca a maior. O trigger usa **`FIELD_TRIGGER_CLASS`** (de `ui/input.tsx`),
   não a escala de botão do projeto — campo de FK herda a métrica de `Input`, não a de `Button`.
   **Scroll dentro de Dialog:** um `useEffect([open])` anexa listeners **nativos não-passivos**
   (`wheel`/`touchstart`/`touchmove`) no `[data-slot="command-list"]` via `ref` no
   `PopoverContent`. Sem isso, o `react-remove-scroll` do Radix Dialog (que portala o popover pra
   fora do lock) engole a roda do mouse e o toque — só a barra escapa. React trata `onWheel` como
   passivo, então `preventDefault` via prop não funciona; o listener nativo reinjeta o scroll
   (`scrollTop += delta`, ciente do `deltaMode`) e respeita o boundary (deixa o chaining seguir).
2. **Wrapper fino por entidade** (~70 linhas, ex. `CustomerPicker`) — injeta o `useList` do hook
   da entidade, fixa `getId`/`getLabel`/`renderItem`, e mantém o state do quick-create.
3. **`*FormDialog` da entidade** (o MESMO dialog de criar/editar da tela de índice) — recebe
   `entity={null}` (modo criação) e **`onSaved(entity)` obrigatório**: o `onSaved` DEVE chamar
   `onChange(id, label, entity)` com o objeto retornado pela mutation, auto-selecionando o registro
   no form pai. Um `*FormDialog` sem callback `onSaved` é **prereq bloqueante** — o quick-create
   não fecha o loop sem ele; adicione antes de plugar o picker.

## Contrato do `useList` (o que o picker exige)

```ts
useList: (params: ListRequest, options: { enabled: boolean }) => { data?: PagedResponse<T> }
// ListRequest: { search?, limit?, skip?, filters?, ... }  ·  PagedResponse<T>: { items, total, skip, limit }
```

Vem do `useCrud(endpoint)` canônico — a versão com `useMemo` no service, `useList(params,
queryOptions)` aceitando `enabled`, e `invalidateQueries([endpoint, "list"])` no `onSuccess` do
`useCreate` (é isso que faz a entidade recém-criada aparecer quando o picker reabre). Um `useCrud`
sem o segundo parâmetro `options`/`enabled` é **prereq bloqueante** — atualize-o antes.

O `useList` do `useCrud` **deve** setar `placeholderData: keepPreviousData` (de
`@tanstack/react-query`). Sem isso, o degrau de `limit` troca a query key, o `data` fica
`undefined` durante o fetch, a lista colapsa pro estado "Carregando…" e o `scrollTop` **volta ao
topo** no meio da paginação. Com `keepPreviousData` a janela anterior fica na tela até a maior
chegar — o scroll não pula. Bônus: tabelas paginadas param de piscar ao trocar página/filtro.
É invariante do `useCrud` de cada projeto (não mora no `entity-picker.tsx`).

## Contrato de backend

O mesmo list endpoint da tela de índice serve o picker — **não** crie endpoint de autocomplete:

```
GET /<recurso>?skip=0&limit=10&search=<texto>   →   PagedResponse[T] { items, total, skip, limit }
```

Repo: `ILIKE '%' || $n || '%'` nas colunas de exibição (nome, documento, telefone, placa…),
`COUNT(*) OVER()` para `total` na mesma query, `ORDER BY` estável, `LIMIT/OFFSET`. Molde:
`customer_repository.list_by_org` do promoservice. (Gate `database` para o SQL.) O `total` **não é
decorativo** — é ele que alimenta o `hasMore` do scroll; sem `COUNT(*) OVER()` o picker nunca
pagina além dos 10 primeiros.

## Wrapper canônico (receita = `CustomerPicker`)

```tsx
export function CustomerPicker({ orgId, value, valueLabel, onChange, placeholder, disabled }: CustomerPickerProps) {
  const [createOpen, setCreateOpen] = useState(false);
  const { useList } = useCustomers(orgId);

  return (
    <>
      <EntityPicker<Customer>
        useList={useList}
        value={value}
        valueLabel={valueLabel}
        onChange={onChange}
        getId={(c) => c.id}
        getLabel={(c) => c.name}
        renderItem={(c) => (
          <>
            <span className="truncate">{c.name}</span>
            {c.phone && <span className="text-muted-foreground ml-auto text-xs">{c.phone}</span>}
          </>
        )}
        placeholder={placeholder ?? "Sem cliente vinculado"}
        searchPlaceholder="Buscar cliente..."
        emptyText="Nenhum cliente encontrado."
        createLabel="Novo cliente…"
        onCreateNew={() => setCreateOpen(true)}
        disabled={disabled}
      />
      {createOpen && (
        <CustomerFormDialog
          orgId={orgId}
          open={createOpen}
          onOpenChange={setCreateOpen}
          customer={null}
          onSaved={(customer) => {
            onChange(customer.id, customer.name, customer); // auto-seleciona no form pai
            setCreateOpen(false);
          }}
        />
      )}
    </>
  );
}
```

- `onChange(id, label, item)` — o form pai geralmente guarda só o `id` (`field.handleChange(id)`
  no TanStack Form, ou `useState<T | null>` quando precisa do item inteiro p/ dados derivados).
- `valueLabel` — label já conhecido em modo edição (evita "carregando" antes da lista chegar).
- A seleção pós-create usa o **objeto retornado pela mutation** (`onSaved`), não um re-fetch da
  lista — funciona mesmo antes da invalidation completar.

## Variações

| Prop / técnica                     | Quando                                                                    |
| ---------------------------------- | -------------------------------------------------------------------------- |
| omitir `createLabel`+`onCreateNew` | Entidade não-criável no fluxo — CTA "Novo…" some sozinho                   |
| `clearable={false}`                | Desvincular proibido (ex.: só na criação: `clearable={!entity}`)           |
| `disabled`                         | Valor herdado imutável (ex.: OS nascida de checklist já tem veículo fixo)  |
| `monoValue`                        | Valor selecionado em fonte mono (placas, códigos)                          |
| `renderItem`                       | Linha rica: label + secundário à direita (telefone, contato, marca/modelo) |
| wrap do `useList` p/ filtro fixo   | `(p, o) => useList({ ...p, filters: { is_active: "true" } }, o)` (SupplierPicker) |
| preset de FK no quick-create       | Prop `presetCustomerId` repassada ao FormDialog (novo veículo já com dono) |

## Receitas de adaptação (quando o backend não bate no contrato)

- **Endpoint fora do padrão** (ex.: `GET /contacts/search?q=` retornando array cru) → adapter no
  hook da entidade que normaliza p/ `{ items, total, skip: 0, limit }` no shape do contrato. O
  picker não muda.
- **Lista bounded já cacheada** (ex.: orgs do admin sem `search` no backend) → wrap com filtro
  **client-side** sobre a query existente. Stopgap consciente: comente a limitação de escala e
  registre o backlog de backend (`q/skip/limit`).
- **API externa só com filtros estruturados** (sem full-text) → picker **bespoke** Popover+Command
  com os filtros reais no header (Selects/faixas) no lugar do `CommandInput` único — NÃO force o
  genérico a fingir busca textual que não existe. Sem quick-create se o inventário é externo.

## Gotchas

- **Foco Popover × Dialog aninhado:** `creatingRef` + `onCloseAutoFocus` com `preventDefault` no
  `PopoverContent` — sem isso o focus-restore do Popover briga com o `onOpenAutoFocus` do Dialog
  do quick-create. Já resolvido no canônico; não remova ao adaptar.
- **Dialog-em-Dialog:** o quick-create abrindo `*FormDialog` por cima de um form que já é Dialog é
  **exceção deliberada e sancionada** (ver `overlays.md`). O FormDialog quase-fullscreen
  (`h-[90vh] w-[92vw] max-w-[min(1100px,92vw)]`) deixa óbvio que é overlay, não navegação.
- **IDs numéricos:** `EntityPicker.value` é `string | null` — converta nas duas pontas
  (`getId={(c) => String(c.id)}`; `onChange={(id) => setId(id ? Number(id) : null)}`).
- **`shouldFilter={false}` é inegociável** — reativar o filtro client-side do cmdk esconde
  resultados válidos do servidor e mata o CTA "Novo…" no estado vazio.
