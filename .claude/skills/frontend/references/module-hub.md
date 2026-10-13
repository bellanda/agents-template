# Hub de módulo (grid de áreas no lugar de N itens na sidebar)

Decisão do usuário 2026-10-13 (Kailos, Financeiro): quando um módulo tem muitas áreas (≥6) a
sidebar não comporta e as configurações somem. O módulo vira UM item na sidebar → rota índice
do módulo = **hub**: grid de cards (ícone + título + 1 linha), um card por área visível ao
usuário, e por último o card "Configurações" (abre `?settings=<seção>` quando tem permissão).

Canônico: kailos `frontend/src/components/finance/hub/FinanceHub.tsx` + `components/sidebar/finance-nav.tsx`
(lista única `FINANCE_NAV_ITEMS` com label/ícone/segmento/permissão/descrição alimenta sidebar,
hub e guards) + `routes/.../financeiro/route.tsx` (layout com link "← Financeiro" em toda
sub-página, escondido no próprio hub).

Invariantes:
- Lista de áreas = fonte ÚNICA (`visibleXNavItems(can)`); hub e guards leem dela, sem duplicar.
- Item da sidebar aparece se o usuário enxerga pelo menos uma área (ou a config).
- Grid por container query: `grid-cols-2` no celular (card compacto `p-3`, título e descrição
  `truncate`), `@2xl/main:grid-cols-3 @4xl/main:grid-cols-4`. Nunca 1 coluna de cards altos.
- Card inteiro clicável (`Link`), foco visível, cor semântica (`bg-card hover:bg-accent`).
- O antigo painel/dashboard do módulo vira uma área (`/<modulo>/painel`), primeiro card.
- Sub-página ganha só o link "← <Módulo>" (layout do módulo), sem breadcrumb gigante.
