# EntityPicker — FK pesquisável + quick-create "Novo…" (OBRIGATÓRIO em todo FK)

> Reference do gate `frontend` (item 8d do checklist). Abra ANTES de colocar qualquer campo de FK
> em um form (selecionar cliente, veículo, fornecedor, contato, organização…). Fonte canônica do
> componente: `references/entity-picker.tsx` (vendored por projeto em
> `components/ui/entity-picker.tsx`, cópia byte-idêntica — depende de `command.tsx`/`popover.tsx`
> shadcn, `cmdk` e `react-icons/lu`). **Wrapper + hook de label canônicos (2026-10-01):** promoservice
> `components/vehicles/CustomerPicker.tsx` + `components/ui/use-picker-label.ts`.

**Princípio (decisão 2026-10-01): TODO campo que grava o id de outra entidade é `EntityPicker`** —
wrapper fino por entidade + `usePickerLabel` + CTA **"Novo…"** que abre o `*FormDialog` da entidade
por cima e **volta selecionado**. É um combobox **pesquisável no servidor** (clica → digita → a
primeira página de 10 vem do backend; rola até o fim ou clica "Carregar mais" e as páginas são **anexadas**); o usuário nunca sai do form
para cadastrar a dependência. FK nunca é `Select` estático nem `Input` de ID cru. E o campo é
**único**: os dados do relacionado vivem NA entidade relacionada (ver **FK limpo**, abaixo).

## Tabela de decisão

| Cenário                                                                         | Use                                                                 |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| FK para entidade do tenant criável no fluxo (cliente, contato, fornecedor, veículo) | **EntityPicker com quick-create** (`createLabel` + `onCreateNew`) |
| FK para entidade do tenant não-criável no fluxo (org no admin, inventário externo)  | EntityPicker **sem** `createLabel`/`onCreateNew` (CTA some)       |
| FK cuja lista é pequena/bounded (membros da org, responsável) ou cujo endpoint não tem `search` | EntityPicker + **adapter** (receitas de adaptação, abaixo) — continua sendo picker |
| Valor que NÃO é registro: enum, status, tipo, opção fixa; catálogo fechado do sistema (papéis/roles) | `Select` — não é FK de entidade do tenant                    |
| Seletor de CONTEXTO global (trocar org/cliente ativo no header/sidebar)         | `DropdownMenu` — não é campo de form                                |

**Critério objetivo:** o campo grava `<algo>_id` de uma tabela do tenant? → EntityPicker, sempre,
mesmo que a lista hoje tenha 5 itens (ela cresce). `<Select>` cru de FK, `Input` de ID/UUID e picker
**sem** "Novo…" onde criar faz sentido são violações a converter na auditoria.

## Anatomia (4 peças)

1. **`EntityPicker<T>` genérico** (`ui/entity-picker.tsx`, canônico) — `<Popover modal>` + Command com
   `shouldFilter={false}` (o servidor decide o recorte; o vazio é `items.length === 0`, nunca o
   auto-hide do `CommandEmpty`, senão o estado vazio perderia o CTA). Busca a cada keystroke via
   `useList({ search }, { enabled: open })` — a query só liga com o popover aberto; TanStack Query
   deduplica/cancela (sem debounce manual). Páginas de 10 (`PAGE_SIZE`) **anexadas** pelo
   `useInfiniteList`/`useInfinitePages`: `useInfiniteScrollSentinel` (scroll de verdade até o fim, sem
   `IntersectionObserver`) + botão ghost "Carregar mais" no fim da lista (lista curta não rola). O
   trigger usa **`FIELD_TRIGGER_CLASS`** (de `ui/input.tsx`), não a escala de botão do projeto.
   - **`<Popover modal>`** resolve a roda do mouse dentro de um Dialog (o `react-remove-scroll` do
     Dialog engolia wheel/touch do popover portalado). Substitui o antigo hack de listeners nativos
     `wheel`/`touchmove` — não reintroduza.
   - **Rodapé fixo FORA da área de scroll**, e a faixa INTEIRA é um único botão: "+ Novo…"
     (`createLabel`) à esquerda, alinhado ao texto dos itens, e "X de Y" muted à direita (`total` do
     source). Sem quick-create, só a contagem. **Nunca** o CTA "Novo" dentro do `CommandList`.
   - **Conteúdo do item em `<span className="flex min-w-0 flex-1 items-center gap-2">`**: o
     `CommandItem` termina num ícone de check com `ml-auto`; sem o `flex-1` um `ml-auto` do
     `renderItem` (telefone, placa) dividia a sobra com ele e a 2ª coluna saía torta.
2. **Wrapper fino por entidade** (~70 linhas, ex. `CustomerPicker`) — injeta o `useList` do hook
   da entidade, fixa `getId`/`getLabel`/`renderItem`, e mantém o state do quick-create. **Um wrapper
   por entidade, reutilizado em todo form** — nunca montar `EntityPicker` cru em tela.
3. **`usePickerLabel`** (`ui/use-picker-label.ts`) — o quick-create devolve uma entidade que **ainda
   não está na página carregada** de `items`; sem cache do label o picker não a acharia e cairia no
   placeholder, parecendo vazio com o `value` já preenchido. O hook lembra o `{id, label}` da última
   seleção/criação e só o usa enquanto casa com o `value` atual; fora disso respeita o `valueLabel`
   do consumidor (modo edição). Todo wrapper o usa: `const { resolvedLabel, handleChange } =
   usePickerLabel<T>(value, valueLabel, onChange)`.
4. **`*FormDialog` da entidade** (o MESMO dialog de criar/editar da tela de índice) — recebe
   `entity={null}` (modo criação) e **`onSaved(entity)` obrigatório**: o `onSaved` DEVE chamar
   `onChange(id, label, entity)` com o objeto retornado pela mutation, auto-selecionando o registro
   no form pai. Um `*FormDialog` sem callback `onSaved` é **prereq bloqueante** — o quick-create
   não fecha o loop sem ele; adicione antes de plugar o picker.

## Contrato do `useList` (o que o picker exige)

```ts
useList: (params: { search?: string }, options: { enabled: boolean }) => EntityPickerSource<T>
// EntityPickerSource<T> = { items: T[]; total: number; hasNextPage: boolean;
//   isFetching: boolean; isFetchingNextPage: boolean; fetchNextPage: () => unknown }
```

É exatamente o shape de retorno de `useInfiniteList`/`useInfinitePages`. Páginas são **APPENDED**:
o desenho antigo (limit crescente de 10 em 10 na query key) fazia cada degrau virar uma key nova e
VAZIA — a lista colapsava em "Carregando…", o scroll voltava ao topo (remendado com
`keepPreviousData`) e o teto do backend (200) cortava a lista. Agora a key é estável por
`search` e o `fetchNextPage` só acrescenta.

### Os 3 adapters

**1. Endpoint de CrudService** → `useInfiniteList(endpoint, params, options)`:

```ts
const useList = (params: { search?: string }, options: { enabled: boolean }) =>
  useInfiniteList<Customer>(`/organizations/${orgId}/customers`, params, options);
```

**2. Endpoint fora do CrudService** (`org_id` em query param etc.) → `useInfinitePages` (canônico:
kailos `hooks/useContacts.ts#useContactSearch`):

```ts
export function useContactSearch(orgId: string) {
  const { client } = useDataProvider();
  return (params: { search?: string }, options: { enabled: boolean }) =>
    useInfinitePages<ContactResponse>({
      queryKey: ["/contacts", "list", orgId, "picker", params.search ?? ""],   // SEM limit/skip na key
      fetchPage: async ({ skip, limit }) =>
        (await client.get<PagedResponse<ContactResponse>>("/contacts", {
          params: { org_id: orgId, search: params.search ?? "", skip, limit },
        })).data,
      enabled: options.enabled,
    });
}
```

**3. Lista bounded em memória** (endpoint devolve o array inteiro, sem `search`/`skip`) → filtra
local (NFD + lower) sobre UMA query cacheada e devolve tudo com `hasNextPage: false` (canônico:
kailos `components/members/MemberPicker.tsx#useOrgMemberSearch`):

```ts
return { items, total: items.length, hasNextPage: false,
         isFetching: query.isFetching, isFetchingNextPage: false, fetchNextPage: NOOP };
```

Stopgap consciente (comente a escala); se o tenant passar de centenas, pagine no backend.

Vem do `useCrud(endpoint)` canônico, cujo `useCreate` invalida `[endpoint, "list"]` no `onSuccess`
(é isso que faz a entidade recém-criada aparecer quando o picker reabre — o prefixo cobre as keys
`infinite` e `paged`).

## Contrato de backend

O mesmo list endpoint da tela de índice serve o picker — **não** crie endpoint de autocomplete:

```
GET /<recurso>?skip=0&limit=10&search=<texto>   →   PagedResponse[T] { items, total, skip, limit, has_more }
```

Repo: `ILIKE '%' || $n || '%'` nas colunas de exibição (nome, documento, telefone, placa…),
`ORDER BY` estável com desempate por `id`, `LIMIT limit+1`/`OFFSET` (sentinela). Molde:
`customer_repository.list_by_org` do promoservice. (Gate `database` → `list-pagination.md` para o
SQL.) O `total` **não é decorativo** — alimenta o "X de Y" do rodapé, e o `has_more` (sentinela) dirige o
`hasNextPage`. `total` é exato em TODA página (`COUNT(*)` separado, **nunca** `COUNT(*) OVER()`),
então o picker pede `skip=10, 20…` sem perder o total.

## Wrapper canônico (receita = `CustomerPicker`)

```tsx
export function CustomerPicker({ orgId, value, valueLabel, onChange, placeholder = "Sem cliente vinculado", disabled }: CustomerPickerProps) {
  const [createOpen, setCreateOpen] = useState(false);
  const { useList } = useCustomers(orgId);
  const { resolvedLabel, handleChange } = usePickerLabel<Customer>(value, valueLabel, onChange);

  return (
    <>
      <EntityPicker<Customer>
        useList={useList}
        value={value}
        valueLabel={resolvedLabel}          // NÃO o valueLabel cru: o cache cobre o recém-criado
        onChange={handleChange}
        getId={(c) => c.id}
        getLabel={(c) => c.name}
        renderItem={(c) => (
          <>
            <span className="truncate">{c.name}</span>
            {c.phone && <span className="text-muted-foreground ml-auto text-xs">{c.phone}</span>}
          </>
        )}
        placeholder={placeholder}
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
            handleChange(customer.id, customer.name, customer); // auto-seleciona no form pai
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

## FK limpo — o relacionado vive na entidade, não no form (regra de 2026-10-01)

**Nunca duplique ao lado do picker os campos da entidade relacionada** (nome, telefone, e-mail,
documento do cliente/contato). Dois lugares para o mesmo dado divergem na primeira edição de um
deles — e o picker vira decoração. O campo de FK é **um só**; o que o usuário precisa ver do
relacionado é um **resumo somente leitura** com um atalho para editar a ENTIDADE:

```tsx
<ContactPicker value={contactId} valueLabel={contact?.name} onChange={(id) => setContactId(id)} />
{contact && (
  <div className="text-muted-foreground flex items-center justify-between gap-3 rounded-md border p-3 text-sm">
    <div className="min-w-0">
      <p className="text-foreground truncate font-medium">{contact.name}</p>
      <p className="truncate">{[formatPhone(contact.phone), contact.email].filter(Boolean).join(" · ")}</p>
    </div>
    <Button type="button" variant="outline" size="sm" onClick={() => setEditOpen(true)}>
      Editar contato                                {/* "Editar <entidade>" */}
    </Button>
  </div>
)}
{editOpen && <ContactFormDialog contact={contact} open onOpenChange={setEditOpen} onSaved={() => setEditOpen(false)} />}
```

- O atalho abre o **mesmo `*FormDialog`** de editar da tela de índice (`entity={obj}`); ao salvar, a
  query da entidade é invalidada e o resumo atualiza sozinho.
- Resumo = texto, não `<Input>`: nada editável inline, nada que "pareça" campo do form atual.
- Sem seleção → só o picker (com "Novo…").
- **Backend espelha:** a tabela guarda **só** `<entidade>_id`. Coluna denormalizada
  (`contact_name`, `contact_phone` ao lado de `contact_id`) é antipadrão: migration dbmate que
  **backfila** (cria/vincula a entidade para os registros que só tinham os campos soltos) e **só
  depois** remove as colunas; DTO devolve o resumo do relacionado por JOIN, e quem lia o campo solto
  (models, repos, prompt do agente) passa a ler da entidade. Gate `database`.
- Única exceção: dado que é **instantâneo histórico** (ex.: nome impresso num documento já emitido,
  que não pode mudar quando o cadastro mudar) — aí a coluna se chama como snapshot (`*_snapshot`) e
  nunca é editada pelo form como se fosse o relacionado vivo.

### Auditoria de FK (rodar em cada app)

```bash
# 1) campos soltos ao lado de FK: colunas/props <entidade>_name|_phone|_email junto de <entidade>_id
rg -n "(contact|customer|client|supplier)_(name|phone|email|document)" backend --glob '*.{sql,py}'
rg -n "(contact|customer|client|supplier)(Name|Phone|Email)" frontend/src --glob '*.tsx'
# 2) <Select> cru de FK (opções vindas de useList/query de entidade)
rg -n "<Select" frontend/src --glob '*.tsx' -l      # abrir cada um: é id de registro do tenant?
# 3) adapter de picker com `limit` crescente na query key (desenho antigo; hoje páginas anexadas)
rg -n "params\.limit|limit: params" frontend/src --glob '*.{ts,tsx}' | rg -i "picker|search"
# 4) picker sem quick-create onde criar faz sentido
rg -n "<EntityPicker|Picker\b" frontend/src --glob '*.tsx' | rg -v "onCreateNew|createLabel"
```

Achado → converter para wrapper + `usePickerLabel` + "Novo…", e remover o campo solto (front + back +
migration).

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

- **Endpoint fora do padrão** (ex.: `GET /contacts/search?q=` retornando array cru) → adapter 2 ou 3
  acima, normalizando para `EntityPickerSource`. O picker não muda.
- **Lista bounded já cacheada** (ex.: orgs do admin sem `search` no backend) → adapter 3.
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
- **IDs numéricos:** `EntityPicker.value` é `string | null` e `getId` TEM de devolver string —
  `String(id)` nas duas pontas (`getId={(c) => String(c.id)}`; `onChange={(id) => setId(id ? Number(id) : null)}`).
- **`shouldFilter={false}` é inegociável** — reativar o filtro client-side do cmdk esconde
  resultados válidos do servidor e mata o CTA "Novo…" no estado vazio.
