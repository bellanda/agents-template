# Primitivas shadcn v4 — armadilhas de quem escreve no idioma v2/v3

## `Card` — a RAIZ manda no ritmo vertical, o slot só no horizontal

No v4 o `Card` é `flex flex-col gap-6 py-6` e os slots são `px-6` SEM padding vertical (no v2/v3 era o
contrário: `Card` vazio e `CardContent` = `p-6 pt-0`). Escrever no idioma antigo sobre a primitiva nova
não substitui o padding — **soma**: `<CardContent className="pt-6">` dá 48px entre header e conteúdo em
vez de 24, e `<CardContent className="py-10">` num estado vazio de uma linha vira 64px.

- **PROIBIDO** `p-*`/`py-*`/`pt-*`/`pb-*` em `CardContent`/`CardHeader`/`CardFooter`.
- Card mais compacto = `<Card className="gap-4 py-4">` + slots `px-4` (a raiz, uma vez, não cada slot).
- `CardFooter` com `border-t` já traz `[.border-t]:pt-6` da base — repetir `py-6` no call site dobra.
- `space-y-*` em `CardHeader` é morto e nocivo: ele é `grid` com `gap-2`, e a margem do `space-y` SOMA
  ao gap.
- Compensação com `py-0` na raiz é legítima só em card com overlay absoluto (imagem full-bleed).

## `<Label>` NÃO é `select-none`

O shadcn marca o label como não-selecionável para que o duplo-clique que alterna um checkbox não pinte a
legenda. O custo é que ninguém consegue copiar o rótulo de um campo — e num formulário longo, arrastar
sobre um bloco misto de label não-selecionável e valor selecionável produz uma seleção que pula pedaços,
que o usuário lê como tela quebrada.

- Remova `select-none` de `components/ui/label.tsx`.
- O `select-none` legítimo é o de superfície inteira clicável (`ToggleCard`, `CardCheckbox`), onde não há
  texto para copiar.

## Campo nativo ≥16px no celular

Todo `<input>`/`<textarea>`/`<select>` de `components/ui/` é `text-base … md:text-sm`. O gatilho do
auto-zoom do iOS é a fonte computada do próprio campo — com `html { font-size: 17px }`, `text-sm` =
14.875px. Detalhe, assinatura e o que NÃO fazer: `mobile-keyboard.md`.
