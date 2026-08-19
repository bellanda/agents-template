# Abas responsivas — 3+ abas viram `Select` no mobile

> Reference do gate `frontend` (item 8g). Componente canônico: `references/tabs.tsx`.

## O problema

Abaixo de 768px uma tira de abas com 3+ itens não cabe em 375px. Só existem dois desfechos, os
dois ruins:

- triggers estouram a largura → **scroll horizontal na página inteira** (o `flex-1` do trigger não
  salva: `whitespace-nowrap` + ícone + rótulo passam do container);
- `flex-wrap` no `TabsList` → a tira empilha em 2–3 linhas e **come metade da tela** antes do
  conteúdo começar.

Rótulo em pt-BR agrava ("Visão geral", "Indicadores", "Oportunidades"). Com 2 abas a tira cabe e o
Select só atrapalha — por isso o corte é **3**.

## A regra

**`TabsList` com 3+ triggers renderiza um `Select` abaixo de 768px.** Não é decisão de call site:
o componente resolve sozinho, contando os filhos. Toda `Tabs` do app ganha isso de graça.

```tsx
// Call site normal — nada de especial. O Select do mobile é automático.
<Tabs value={tab} onValueChange={setTab}>
  <TabsList>
    <TabsTrigger value="overview"><LuLayoutDashboard /> Visão geral</TabsTrigger>
    <TabsTrigger value="aging"><LuGauge /> Aging</TabsTrigger>
    <TabsTrigger value="kpis"><LuChartNoAxesCombined /> Indicadores</TabsTrigger>
  </TabsList>
  …
</Tabs>
```

## Como funciona (e por que assim)

1. **`TabsValueContext`** — `Tabs` espelha o valor ativo num context só para o `TabsList` alimentar
   o Select. `value`/`defaultValue` seguem intactos para o `TabsPrimitive.Root`: quem manda no
   controle continua sendo o Radix, o espelho só acompanha o que ele já decidiu (atualiza no
   `onValueChange` que o próprio Root dispara). Controlado e não-controlado funcionam igual.
2. **`collectTabItems(children)`** — lê os triggers da árvore para espelhar rótulo/`disabled` no
   Select. Desce em fragments, arrays e wrappers finos (`SandboxTabsTrigger`, `TooltipTrigger
   asChild`); o critério é **ter `value` string**, não ser literalmente `TabsTrigger`.
3. **A troca é CSS.** As duas formas montam sempre: `md:hidden` no trigger do Select,
   `max-md:hidden` na tira. **NUNCA `useIsMobile()`** — ele resolve em `useEffect`, então o primeiro
   frame no celular renderiza a tira e pisca, e a troca de árvore **remonta o painel ativo** (perde
   scroll, refaz query, derruba observer). Mesmo motivo do `DataList` (`list-screen.md`).

## API de escape (duas props, use com parcimônia)

| Prop                | Quando                                                                                                                                                                     |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mobile="strip"`    | Aba ícone-only ou rótulo de 1 palavra que cabe em 375px mesmo com 3+ itens (ex.: `Dia`/`Semana`/`Mês`). Mantém a tira no mobile.                                          |
| `selectClassName`   | Classe do **trigger do Select**. `className` não serve — ele estiliza a tira (`flex-wrap`, `gap`, `h-auto`) e não faz sentido no combobox. Use quando a lista divide uma linha flex com um vizinho e o `w-full` default esmagaria o vizinho. |

```tsx
// A lista divide a linha com um vizinho: no mobile o Select ocupa a fatia flex, não 100%.
<div className="flex items-center gap-2">
  <TabsList variant="ghost" className="h-auto flex-1 flex-wrap gap-1" selectClassName="flex-1">
    …
  </TabsList>
  <NegotiationHistory vehicleId={id} />
</div>
```

## PROIBIDO

- ❌ **`isMobile ? <Select…> : <TabsList…>` no call site** — é o padrão que este componente
  substitui. Duplica a lista de abas, resolve em `useEffect` (flash + remount) e o próximo dev
  esquece de replicar. Se encontrar, **apague o ramo e deixe `<TabsList>` puro**.
- ❌ `overflow-x-auto` na tira "pra caber no mobile" — scroll horizontal de navegação esconde aba,
  não resolve.
- ❌ Duplicar a fonte de verdade das abas (um array pro Select, JSX pra tira).
- ❌ `mobile="strip"` como default por preguiça de conferir o rótulo em 375px.

## Auditoria

```bash
rg -n "isMobile \?" frontend/src --glob '!**/ui/sidebar.tsx'   # tabs/tabelas com switch em JS
rg -n "<TabsList" frontend/src --glob '!**/ui/**'              # confirmar que o dual-render cobre
```

Achou `isMobile ? <Select` perto de um `TabsList`? → apagar o ramo mobile, deixar `<TabsList>`,
remover `useIsMobile` e os imports de `Select*` que ficarem órfãos (o `tsgo` acusa: `TS6133`/`TS6192`).
