# Settings Dialog — hub de configurações deep-linkado

> Reference do gate `frontend`. Consolida itens de configuração dispersos da sidebar num único
> Dialog grande com nav lateral + busca (estilo "Claude GUI Settings"). O mecanismo de deep-link
> é o de `overlays.md > Dialog deep-linkado via search param`.
> **Padrão em TODOS os apps de multi-tenant (kailos, balizap, nexarena, akmeo, promoservice) —
> exceto optimuslar (decisão 2026-10-01).** Canônico: **kailos** `components/settings/*`
> (`SettingsDialog.tsx`, `SettingsNav.tsx`, `sections-config.ts`, `sections/*`, `components/members/*`).

## Quando usar

- Sidebar com 2+ itens de configuração/administração (Membros, Equipes, Integrações, Atendente IA,
  Configurações da empresa, marca…) → consolidar num ÚNICO item "Configurações" que abre o hub.
- **Tudo que é "configuração da org" mora no hub**: empresa/marca (branding, logo), membros e
  convites, equipes, agente de IA, integrações, horário, preços. Rota-página própria de config
  (`/o/$id/membros`, `/empresa`, `/configuracoes`) não existe mais — promoservice migra o que é
  rota para o hub (Membros → seção `members`; Empresa/branding → seção `identification`).
- As rotas-página antigas são **REMOVIDAS** (sem redirect/shim); o gate de permissão migra do
  `beforeLoad` das rotas para o `gate` da seção.
- O componente monta na CASCA autenticada (junto do `<Outlet/>`), disponível em qualquer rota.
- **Param** `?settings=<section>` validado no `validateSearch` do layout `_authenticated`
  (`isSettingsSectionId(search.settings) ? search.settings : undefined` — valor inválido = fechado).
  Sufixo `?platform=` do painel de superusuário segue o mesmo desenho (um hub por param).

## Anatomia

```tsx
<Dialog open={!!section} onOpenChange={(o) => !o && close()}>
  <DialogContent className="flex h-[85vh] w-full max-w-[calc(100%-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl lg:max-w-6xl">
    <DialogTitle className="sr-only">Configurações</DialogTitle>
    <div className="flex h-full min-h-0">
      {/* nav esquerda (desktop) */}
      <aside className="hidden w-60 shrink-0 flex-col border-r sm:flex">
        <div className="p-3">{/* <Input> busca/filtro de seções */}</div>
        <nav className="flex-1 overflow-y-auto">{/* grupos + botões */}</nav>
      </aside>
      {/* painel direito — ÚNICO lugar com scroll. A BARRA (header) existe nos DOIS
          tamanhos: título da seção ativa + `HelpButton` (“Como funciona”, `ml-auto`) —
          decisão 2026-10-01, o kailos já é assim. O botão Menu (abre a nav) é que
          continua `sm:hidden`. `pr-12` reserva o X do Dialog. */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b px-4 py-3 pr-12">
          <Button variant="ghost" size="icon-sm" className="sm:hidden" aria-label="Todas as seções" />
          <h2 className="truncate text-sm font-medium">{active.label}</h2>
          <HelpButton key={active.id} topic={settingsHelpTopic(active.id)} className="ml-auto" />
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">{/* só a seção ativa monta */}</div>
      </main>
    </div>
  </DialogContent>
</Dialog>
```

- Altura **FIXA** `h-[85vh]` (não `max-h`): nav estável entre seções; scroll SÓ no painel direito.
- `lg:max-w-6xl` (1152px) = "boa parte da tela sem ser fullscreen". Não negociar por seção —
  tamanho ÚNICO do hub.
- Nav = grupos (label de grupo + itens) com `<button data-active>` + ícone `react-icons`.
  **NÃO** `Tabs/TabsTrigger` do shadcn (grupos + filtro não cabem no modelo do Tabs).
- **Nav compacta em px FIXOS no desktop** (estilo Claude GUI: 10+ seções visíveis SEM scroll na
  nav). Itens `sm:min-h-0 sm:py-1.5 sm:text-[13px]`, ícone `sm:size-3.5`, label de grupo
  `sm:text-[11px]`, busca `sm:h-8 sm:text-[13px] md:text-[13px]` (o `md:` é obrigatório — o
  Input base tem `md:text-sm` que venceria o `sm:`), gap pequeno busca→lista (`sm:pt-1` na nav),
  espaçamento `sm:space-y-3 sm:px-2`. Px fixo (não rem) de propósito: a nav NÃO acompanha o
  `html { font-size: 17px }` do app — só o painel de conteúdo escala. Mobile mantém `min-h-11`
  (touch ≥44px).
- Busca: `useState` local filtrando por label (case-insensitive); grupo sem match some.
- **Lazy mount**: só a seção ativa monta (`switch (active.id)` num `NonOrgSection`) — nunca montar todas.
- **Tenant do hub = `organizationStore`** (o seletor global, ver `app-scaffold`):
  `useSyncExternalStore(subscribe, getSelectedOrgId)`; as seções recebem `orgId` por **prop**
  (`<MembersSection orgId={orgId} />`) — **NUNCA** `Route.useParams` (o hub vive na casca, fora da
  rota da entidade). `key={orgId}` no corpo para remount limpo ao trocar de org. Sem org
  selecionada o corpo mostra "Selecione uma organização para continuar.".
- **`HelpButton`** (“Como funciona”): `key={active.id}` + `settingsHelpTopic(active.id)` (kailos
  `components/help/*`). App sem sistema de ajuda mantém a barra só com o título.

## Estrutura de arquivos (cópia do kailos)

```
src/components/settings/
  SettingsDialog.tsx      ← casca: lê `?settings=`, useCurrentOrgRoles, fallback, header, corpo
  SettingsNav.tsx         ← busca + grupos + botões (reuso desktop/mobile)
  sections-config.ts      ← SETTINGS_SECTION_IDS, SETTINGS_GROUPS, SETTINGS_SECTIONS, getVisibleSections()
  sections/<Name>Section.tsx  ← um arquivo por seção (recebe `{ orgId }`)
  sections/OrgTabSection.tsx  ← abas de dados da org (render "org-tab"): Empresa, Preços, Horário…
  sections/queues/*       ← editor de Equipes (ver `queues-editor.md`)
src/components/members/   ← Membros e convites (ver "Membros e convites" abaixo)
```

### `sections-config.ts` — DADO, não condicional na casca

```ts
export interface SettingsSection {
  id: SettingsSectionId;            // união literal derivada de SETTINGS_SECTION_IDS (também valida a URL)
  label: string;                    // pt-BR
  group: SettingsGroup;             // "Primeiros passos" | "Organização" | "IA" | "Conexões"
  icon: IconType;                   // react-icons/lu
  gate: "org-settings" | "members" | "queues" | "agent" | "insights" | "portals";
  render: "org-tab" | "standalone"; // QUEM renderiza — nunca deduza pelo nome do grupo
}
export function getVisibleSections(can: (p: Permission) => boolean, isAdminLevel: boolean): SettingsSection[];
```

- **`render` é dado.** O kailos decidia por `group === "Organização"` e uma aba de org no grupo
  "IA" abria em branco. `org-tab` = a casca carrega a org (`useGet(orgId)`) e entrega ao
  `OrgTabSection`; `standalone` = seção que busca o próprio dado (`NonOrgSection`).
- A ordem do array = ordem da nav = ordem do tour de onboarding ("passo N de M"). Primeiros passos
  no kailos: Empresa → Membros → Equipes → Atendente de IA → WhatsApp (a IA precisa das equipes
  para transferir; o número só liga depois de haver quem atenda).
- Cada app mantém **suas** seções/gates (balizap/nexarena/akmeo/promoservice têm conjuntos
  diferentes); o que é padrão é o **mecanismo** (`id/label/group/icon/gate/render` +
  `getVisibleSections`) e a casca.

## Mobile (375px) — nav sobreposta ao painel

Sub-estado local `mobileNavOpen`: o botão **Menu** (`LuMenu`, `aria-label="Todas as seções"`, só
`sm:hidden`) do header abre a nav em tela cheia sobre o painel (`pt-8`, painel `hidden sm:flex`);
escolher uma seção fecha a nav e mostra o painel — o dialog **não** fecha. Touch ≥44px. Não usar
`<select>` no topo — esconde grupos e busca.

## Permission gating

- O `gate` da seção mapeia para **a permissão que o backend cobra**, não para papel:
  `members → MEMBER_MANAGE`, `queues → QUEUE_MANAGE`, `agent → AGENT_CONFIG_MANAGE`,
  `org-settings → ORG_SETTINGS`, `insights → INSIGHTS_MANAGE`, `portals → PORTAL_MANAGE`.
  `isAdminLevel` entra só no OR de `members`/`queues` (bypass de superusuário sem vínculo na org) —
  conceder `member:manage` avulso a um supervisor precisa abrir a seção.
- Gate é lido de `useCurrentOrgRoles()` (`{ can, isAdminLevel, isSuperuser }`), ver `app-scaffold`
  ("permissão em 2 níveis"). Sem permissão a seção **SOME** da nav (não mostra estado vazio).
- `?settings=` apontando seção não permitida (link de terceiro) → `useEffect` com `replace: true`
  leva à primeira seção visível; nenhuma visível → dialog fecha e o item da sidebar nem renderiza.
- Hub não gateia a **API**: o backend recusa de qualquer jeito (403); o gate esconde UI.

## Membros e convites (seção `members` — padrão kailos)

Fonte: `components/settings/sections/MembersSection.tsx` + `components/members/*`. Todos os apps com
equipe adotam o mesmo fluxo; só o conjunto de papéis/permissões varia.

- `MembersSection({ orgId })`: cards de membros (`MemberCard`, avatar `MemberAvatar`/
  `MemberAvatarMenu` com upload/remoção de foto), contador de convites pendentes, botões **Convidar
  por e-mail** (`InviteDialog`) e **Gerar link** (`InviteLinkDialog` mostra o link copiável; reemitir
  = `useReissueInviteLink`). Dados por `useAdminPermissions()` (`useListOrgMembers`,
  `useListOrgInvites`, `useListRoles`, `useListPermissions`, `useCreateInvite`,
  `useUpdateMemberPermissions`, `useRemoveUserFromOrg`…).
- Clique no card → `MemberDetailDialog` (papel + permissões efetivas — `EffectivePermissions`,
  `PermissionPickerColumns`, `RoleInfoDialog`; ver `agent-instructions.md` para o mesmo picker em
  colunas). O dialog guarda **`activeMemberId`**, não snapshot do membro (depois de trocar foto ou
  papel ele lê a lista nova).
- Acesso é **só por convite**: login Google ou a senha que a pessoa cria pelo link. Sem "criar usuário
  com senha" pelo admin.
- `canManage = can(PERMISSIONS.MEMBER_MANAGE)` decide se os botões existem; quem só lê vê cards sem ações.
- Rota-página de membros (`/o/$id/membros` do promoservice, `admin/members` do nexarena) é **removida**
  quando a seção entra no hub.

## Variante org-scoped (hub por-entidade, sem store global)

Só para app SEM seletor global de org (hub aberto a partir da página de uma entidade). Dois params
validados **JUNTOS** — `settings` + `settingsOrg`; um sem o outro → ambos `undefined` (fechado). A
entidade-alvo vem 100% do param. App com `organizationStore` (todos hoje) usa o padrão principal.

## Sub-navegação interna

- Seção que precisa de "lista → editar" mantém a lista (grid de cards) **dentro da seção** e abre o
  editor como Dialog por cima (Equipes: `queues-editor.md`; `editing: Queue | "new" | null` em
  `useState`). Não há tela de detalhe dentro do hub e nunca rota.
- Dialogs de ação (detail/confirm/create/invite) abrem POR CIMA do hub com `useState` local —
  ver don'ts de `overlays.md` (hub→ação efêmera é o caso permitido de Dialog-em-Dialog).
- `PortalCredentialsDialog`/`InviteLinkDialog` seguem o mesmo molde (abrem por cima, fecham sem tocar na URL).

## Don'ts

- **NUNCA** manter rotas-página antigas como redirect/shim — remoção direta.
- **NUNCA** Tabs do shadcn como nav do hub.
- **NUNCA** seção lendo `Route.useParams`.
- **NUNCA** scroll no `DialogContent` inteiro (header/nav saem da tela) — scroll é do painel.
- **NUNCA** `max-w` variando por seção — o hub tem tamanho único.
- **NUNCA** decidir quem renderiza a seção pelo nome do grupo — é o campo `render`.
- **NUNCA** gate por papel (`role === "admin"`) na seção — permissão que o backend cobra (+ `isAdminLevel` só no bypass).
- **NUNCA** manter `/membros`, `/empresa` ou `/configuracoes` como página quando a seção já está no hub.
- **NUNCA** hub próprio em optimuslar (decisão 2026-10-01: fica fora do padrão).
