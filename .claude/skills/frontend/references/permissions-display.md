# Permissões/RBAC — display agrupado por domínio, badges por verbo

> Reference do gate `frontend` (item 8b do checklist). Abra ANTES de renderizar qualquer lista de
> permissões (Dialog de info de função, aba "Efetivas", catálogo, role template). Vale para
> qualquer projeto com RBAC — chaves `dominio:verbo` (PermissionScope) ou matriz
> resource×action (lakehouse).

**Princípio:** nuvem plana de badges é ilegível a partir de ~10 permissões — o usuário não acha
nada e tudo parece igual. O display canônico é **linha a linha, agrupado por conjunto/domínio**:
header do grupo (label pt-BR + count) e, dentro do grupo, badges pequenos **coloridos pelo VERBO**
(último segmento `:` da chave) em ordem canônica. Como RBAC tende a CRUD, o verbo carrega cor,
ícone e ordem fixos — iguais em todos os projetos.

## Tabela canônica de verbos (ordem · cor · ícone · pt)

| verbo               | order | cor       | ícone (lucide / react-icons-lu)   | pt                      |
| ------------------- | ----- | --------- | --------------------------------- | ----------------------- |
| `read` / `view`     | 10    | `sky`     | `Eye` / `LuEye`                   | Ver                     |
| `read_all`          | 11    | `sky`     | `Eye` / `LuEye`                   | Ver todas               |
| `query`             | 15    | `cyan`    | `Search` / `LuSearch`             | Consultar               |
| `create`            | 20    | `emerald` | `Plus` / `LuPlus`                 | Criar                   |
| `generate`          | 25    | `emerald` | `FileOutput` / `LuFileOutput`     | Gerar                   |
| `update`            | 30    | `amber`   | `Pencil` / `LuPencil`             | Editar                  |
| `settle`            | 35    | `lime`    | `HandCoins` / `LuHandCoins`       | Dar baixa               |
| `delete`            | 40    | `rose`    | `Trash2` / `LuTrash2`             | Excluir                 |
| `cancel`            | 45    | `orange`  | `Ban` / `LuBan`                   | Cancelar                |
| `manage`/`settings` | 50    | `violet`  | `Settings2` / `LuSettings2`       | Gerenciar / Configurar  |
| `send`              | 55    | `blue`    | `Send` / `LuSend`                 | Enviar                  |
| `withdraw`          | 56    | `fuchsia` | `Banknote` / `LuBanknote`         | Sacar                   |
| `approve`           | 60    | `teal`    | `BadgeCheck` / `LuBadgeCheck`     | Aprovar                 |
| `approve_edit`      | 61    | `teal`    | `BadgeCheck` / `LuBadgeCheck`     | Aprovar edição          |
| `execute`           | 65    | `indigo`  | `Play` / `LuPlay`                 | Executar                |
| `checkin`           | 66    | `indigo`  | `TicketCheck` / `LuTicketCheck`   | Check-in                |
| `admin` (lakehouse) | 70    | `violet`  | `ShieldCheck` / `LuShieldCheck`   | Admin                   |
| fallback            | 99    | `slate`   | `KeyRound` / `LuKey`              | (verbo cru)             |

A tabela é a **união** do que os projetos usam — cada um copia o arquivo inteiro, não um subconjunto.
Verbo que existe no catálogo Pydantic e falta aqui cai no fallback e **imprime o verbo cru em
inglês no badge** (`read_all`, `generate`): é violação de pt-BR, não detalhe cosmético. Ao criar
`PermissionScope` com verbo novo, adicione na mesma PR. Cor repetida entre verbos da mesma família
(`read`/`read_all`, `execute`/`checkin`, `create`/`generate`) é proposital; o que **não** pode
repetir é o `order`.

Classes do badge por cor `{c}` (light+dark, shades oklch-safe — precedente DeltaChip):

```
border-{c}-200 bg-{c}-50 text-{c}-700 dark:border-{c}-900 dark:bg-{c}-950/40 dark:text-{c}-300
```

Icon lib segue o projeto (kailos members usa `lucide-react`; projetos react-icons usam o set `lu`
equivalente). Os NOMES e cores são o padrão — a lib é detalhe local.

## Metadata mora no Pydantic (backend = fonte única)

O catálogo `PermissionInfo` (em `models/auth/permission_scope_jsonb.py`) carrega o display
metadata; o frontend NUNCA re-deriva grupo/label:

```python
class PermissionInfo(BaseModel):
    permission: str   # "vehicle:read" — verbo = último segmento ":"
    pt: str           # label da permissão
    group: str        # chave do domínio ("vehicle") — granulares 3-segmentos colapsam no pai
    group_pt: str     # label pt-BR do conjunto ("Veículos")
    order: int        # índice global de declaração (passos de 10) — ordena os GRUPOS
```

- `GET /organizations/admin/permissions` retorna o shape enriquecido **tipado**
  (`response_model=list[AdminPermissionResponse]` com `permission, pt, group, group_pt, order`).
  Sem campo `name` morto, sem dict cru.
- Verbo NÃO é armazenado — deriva de `permission.split(":")[-1]` (1 helper compartilhado por lado).
- Chave 3-segmentos (`vehicles:stock:create`) → `group` do domínio pai (`vehicle`); o sub-contexto
  vive no `pt` ("entrada de estoque").

## Arquivos canônicos (vendorados aqui — copie, não reescreva)

| Reference neste diretório       | Vira, no projeto                             |
| ------------------------------- | -------------------------------------------- |
| `permission-verbs.ts`           | `components/members/permissionVerbs.ts`      |
| `group-permissions.ts`          | `components/members/groupPermissions.ts`     |
| `permission-search.ts`          | `components/members/permissionSearch.ts`     |
| `permission-search-input.tsx`   | `components/members/PermissionSearchInput.tsx` |
| `permission-group-list.tsx`     | `components/members/PermissionGroupList.tsx` |
| `permission-picker-columns.tsx` | `components/members/PermissionPickerColumns.tsx` |
| `effective-permissions.tsx`     | `components/members/EffectivePermissions.tsx` |
| `grant-lock.ts`                 | `components/members/types.ts`                |

Os 8 são **idênticos** nos projetos. O que varia por projeto vive só em `MemberDetailDialog.tsx`
(monta o `GrantLock`/`onRemove`) e `InviteDialog.tsx` (payload + papel default) — ver "Seams".

## Componente canônico — `PermissionGroupList`

Vendored em `components/members/PermissionGroupList.tsx` + `permissionVerbs.ts` (fonte: kailos).

```tsx
interface PermissionGroupListProps {
  permissions: string[];                 // chaves a exibir
  catalog: AdminPermission[];            // catálogo do GET /permissions (pt/group/groupPt/order)
  overrideKeys?: Set<string>;            // marca "• override" no badge (aba Efetivas)
  emptyText?: string;
}
```

Regras de render: grupos ordenados por `min(order)` dos itens; itens dentro do grupo por
`verbMeta().order` → tiebreak pela chave; cada grupo = header (`group_pt` + count) numa linha +
badges `variant="outline"` com `gap-1`, ícone `h-3 w-3`, label `pt`, `title={permission}` (chave
crua no tooltip). Consumidores: Dialog Info da função (`sm:max-w-2xl`, nunca `max-w-md`) e aba
Efetivas (mantém linha de totais + computação client-side espelhando
`resolve_membership_permissions`).

## Picker de concessão = mesmo display, só que clicável

As duas colunas "Disponíveis"/"Atribuídas" da aba de conceder usam **o mesmo agrupamento, a mesma
ordem e as mesmas cores** do display read-only. Lista chapada em preto e branco ao lado de uma aba
"Efetivas" agrupada e colorida faz o usuário escolher no escuro e só ver o resultado legível depois
de salvar. O agrupamento mora em `groupPermissions(keys, catalog)` (módulo próprio), consumido
tanto por `PermissionGroupList` quanto pelas colunas — nunca reimplementado nos dois lugares.

Cada linha da coluna: badge do verbo (ícone + cor) + `pt` + a chave crua em `<code>`; header do
grupo com `group_pt` + count; chevron de direção no hover. Grupo que ficou sem item some.

## Busca

Uma barra de busca **por aba** (Funções, Permissões, Efetivas), filtrando as **duas** colunas ao
mesmo tempo — não uma por coluna. É `useState` local do dialog: filtro de overlay é rascunho
efêmero, não estado de tela de coleção (a regra de filtro-na-URL vale para `ListToolbar`/`DataList`,
não aqui), e não há request envolvido — o catálogo já veio inteiro.

Matching normalizado (NFD + strip de diacrítico + lower) sobre **`pt` + chave + `group_pt` + label
do verbo** — quem digita "veic" tem que achar "Veículos", quem digita "delete" tem que achar
"Excluir", e quem cola `vehicle:read` tem que achar o item. O input é `Input` do projeto com
`text-base md:text-sm` (auto-zoom do iOS) e botão de limpar.

## Superusuário

Superusuário não tem papel na org — o bypass vive no backend (`AuthContext.has_permission` retorna
`True` antes de olhar a membership). Um cálculo client-side que só soma papéis + overrides
renderiza **vazio** para ele, dizendo exatamente o contrário da verdade ("nenhuma permissão" para
quem pode tudo).

Contrato: o membro carrega `is_superuser` (`SELECT u.is_superuser` no `get_members_by_org_id` +
campo no response schema + `isSuperuser` no tipo do front). A aba Efetivas ramifica: superusuário →
catálogo INTEIRO + banner "acesso total (bypass de RBAC)", e as marcações de `• override` perdem o
sentido. O front **espelha** a regra do backend, não inventa uma segunda.

## Seams por projeto (o que impede a cópia de forkar em silêncio)

Os arquivos de `components/members/` são copiados entre projetos à mão. Qualquer chave de papel
(`"gestor"`, `"owner"`) ou nome de campo específico (`subscriptionActive`, `organizerStatus`)
dentro de um arquivo compartilhado vira fork silencioso na próxima cópia — sem erro de compilação,
sem lint. Já aconteceu: `PermissionPickerColumns.tsx` divergiu por 2 linhas entre dois projetos.

Duas costuras, ambas declaradas em `components/members/types.ts` e preenchidas SÓ pelo
`MemberDetailDialog` de cada projeto:

```ts
/** Gate de papel/permissão privilegiada no picker. Nada abaixo de
 *  PermissionPickerColumns pode citar chave de papel ou campo de projeto. */
export interface GrantLock {
  isRoleLocked: (role: RoleItem) => boolean;
  isPermLocked: (perm: PermItem) => boolean;
  roleLockMessage: (role: RoleItem) => string;
  permLockMessage: (perm: PermItem) => string;
}
export const NO_LOCK: GrantLock = { /* tudo liberado */ };
```

E a remoção como callback (`onRemove: () => Promise<void>` + `removePending: boolean`), nunca o
objeto da mutation — há projeto sem endpoint de DELETE de membro, e amarrar o dialog ao
`useRemoveUserFromOrg` torna o arquivo não-copiável.

Depois disso, `diff -r` entre os `components/members/` de dois projetos só pode acusar
`MemberDetailDialog.tsx` (monta o `GrantLock`/`onRemove`), `InviteDialog.tsx` (papel default e
shape do payload) e `permissionVerbs.ts` (verbos extras). Qualquer outro arquivo divergindo é bug.

## Dialog de tabs com larguras estáveis

Dialog multi-abas (Perfil/Funções/Permissões/Efetivas) usa **UM tamanho fixo** para todas as abas
(`flex h-[85vh] max-h-[92vh] flex-col sm:max-w-5xl`) — NUNCA `max-w` por aba com transition (o
dialog "pula" e a aba curta colapsa). Aba de conteúdo curto (Perfil) preenche com grid 2-col de
blocos rotulados, não com coluna magra solta. Linha de totais (aba Efetivas) é UMA frase corrida
alinhada à esquerda com separador ` · ` — NUNCA `justify-between` empurrando o sufixo pra borda.

## Don'ts

- **NUNCA** nuvem plana de badges para listas de permissões — sempre agrupado por domínio.
- **NUNCA** cor/ícone ad-hoc por permissão — a cor é do VERBO, pela tabela canônica.
- **NUNCA** label/grupo hardcoded no frontend — `pt`/`group_pt`/`order` vêm do catálogo Pydantic.
- **NUNCA** `max-w` por aba em Dialog de tabs — tamanho único fixo.
- **NUNCA** endpoint `/permissions` retornando dict cru — `response_model` tipado.
- **NUNCA** armazenar o verbo — deriva do último segmento da chave.
- **NUNCA** picker de concessão chapado (sem grupo/cor) ao lado de um display agrupado — os dois lados usam `groupPermissions`.
- **NUNCA** lista de permissões/funções sem busca — a partir de ~20 itens o dual-list vira rolagem cega.
- **NUNCA** busca por `includes` cru — normalize acento/caixa e case também a chave e o label do verbo, não só o `pt`.
- **NUNCA** calcular efetivas ignorando `is_superuser` — renderiza "nenhuma permissão" pra quem pode tudo.
- **NUNCA** chave de papel (`"gestor"`/`"owner"`) ou campo de projeto dentro de arquivo compartilhado — é `GrantLock`.
- **NUNCA** passar o objeto da mutation de remoção pro dialog — é `onRemove` + `removePending`.
