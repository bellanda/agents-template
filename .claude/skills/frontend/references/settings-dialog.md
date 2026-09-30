# Settings Dialog — hub de configurações deep-linkado

> Reference do gate `frontend`. Consolida itens de configuração dispersos da sidebar num único
> Dialog grande com nav lateral + busca (estilo "Claude GUI Settings"). O mecanismo de deep-link
> é o de `overlays.md > Dialog deep-linkado via search param`.

## Quando usar

- Sidebar com 2+ itens de configuração/administração (Membros, Equipes, Integrações, Atendente IA,
  Configurações…) → consolidar num ÚNICO item "Configurações" que abre o hub.
- As rotas-página antigas são **REMOVIDAS** (sem redirect/shim); o gate de permissão migra do
  `beforeLoad` das rotas para a nav do hub.
- O componente monta na CASCA autenticada (junto do `<Outlet/>`), disponível em qualquer rota.

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
      {/* painel direito — ÚNICO lugar com scroll. SEM barra de título no
          desktop: o título vem do conteúdo da seção (senão duplica — "Metas e
          SLA" duas vezes) e o X do Dialog fica solto no canto, estilo Claude
          GUI. O header é mobile-only (sm:hidden), só para o botão Menu da nav. */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b px-4 py-3 pr-12 sm:hidden">
          {/* Botão Menu (abre a nav) + label da seção ativa */}
        </header>
        <div className="flex-1 overflow-y-auto p-4 sm:p-6">{/* só a seção ativa monta */}</div>
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
- **Lazy mount**: `{section === "members" && <MembersSection />}` — nunca montar todas as seções.
- Sections leem o tenant (orgId) de store/prop — **NUNCA** `Route.useParams` (o hub vive na casca,
  fora da rota da entidade). `key={orgId}` no corpo para remount limpo ao trocar tenant.

## Estrutura de arquivos

```
src/components/settings/
  SettingsDialog.tsx      ← casca: lê o param, gating, split nav/painel
  SettingsNav.tsx         ← busca + grupos + botões (reuso desktop/mobile)
  sections-config.tsx     ← SETTINGS_SECTIONS (id, label, icon, group, gate) + getVisibleSections()
  sections/<Name>Section.tsx  ← um arquivo por seção (conteúdo migrado das páginas antigas)
```

## Mobile (375px) — lista → detalhe

Sub-estado local (`mobileShowNav`): sem seção escolhida → lista de seções full-width com busca;
escolhida → painel com botão voltar (`ArrowLeft`) que retorna à lista SEM fechar o dialog.
Touch ≥44px. Não usar `<select>` no topo — esconde grupos e busca.

## Permission gating

- Mapa seção→permissão em `sections-config`; sem permissão a seção **SOME** da nav (não mostra
  estado vazio).
- `?settings=` apontando seção não permitida (link de terceiro) → fallback para a primeira seção
  visível; nenhuma visível → dialog fecha e o item da sidebar nem renderiza.

## Variante org-scoped (hub por-entidade, sem store global)

Dois params validados **JUNTOS** — `settings` + `settingsOrg`; um sem o outro → ambos `undefined`
(fechado). A entidade-alvo vem 100% do param.

## Sub-navegação interna

- Conteúdo lista→detalhe dentro de uma seção (ex.: Equipes) usa `useState` interno
  (`selectedId: string | null`), não rota.
- Dialogs de ação (detail/confirm/create) abrem POR CIMA do hub com `useState` local —
  ver don'ts de `overlays.md` (hub→ação efêmera é o caso permitido de Dialog-em-Dialog).

## Don'ts

- **NUNCA** manter rotas-página antigas como redirect/shim — remoção direta.
- **NUNCA** Tabs do shadcn como nav do hub.
- **NUNCA** seção lendo `Route.useParams`.
- **NUNCA** scroll no `DialogContent` inteiro (header/nav saem da tela) — scroll é do painel.
- **NUNCA** `max-w` variando por seção — o hub tem tamanho único.
