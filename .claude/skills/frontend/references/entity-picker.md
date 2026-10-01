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
primeira página de 10 vem do backend, rola pra puxar mais de 10 em 10); o usuário nunca sai do form
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
`ORDER BY` estável com desempate por `id`, `LIMIT limit+1`/`OFFSET` (sentinela). Molde:
`customer_repository.list_by_org` do promoservice. (Gate `database` → `list-pagination.md` para o
SQL.) O `total` **não é decorativo** — é ele que alimenta o `hasMore` do scroll; o picker sempre
manda `skip=0`, e `total` exato em `skip == 0` (via `COUNT(*)` separado, **nunca** `COUNT(*) OVER()`)
é justamente o contrato do backend — por isso o picker não precisa de nada além do endpoint da lista.

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
# 3) picker sem quick-create onde criar faz sentido
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
