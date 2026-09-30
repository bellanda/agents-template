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

1. **`TabsValueContext`** — `Tabs` mantém um espelho do valor ativo e **DIRIGE o Radix com ele**:
   `<TabsPrimitive.Root value={current}>`, onde `current = value ?? estadoInterno`. Isso não é
   detalhe de implementação, é a condição para o Select funcionar: **o Select NÃO é um
   `TabsTrigger`** — ele chama o `setValue` do context. Se o Root ficar em `defaultValue`, o estado
   interno do Radix só muda por clique num trigger, e no call site **não controlado**
   (`<Tabs defaultValue="…">`) o Select troca o RÓTULO e o painel continua na primeira aba. O call
   site controlado disfarça o bug: o `onValueChange` sobe pro `useState` do call site e volta como
   `value`, então parece que funciona — e só o não controlado quebra, só no celular. Com o espelho
   no comando os dois modos andam igual de verdade.
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

## Navegação por ROTA (seções de um recurso) — mesma regra

Seções que são rotas (`/events/$id`, `/events/$id/dashboard`, `/events/$id/results`…) costumam
nascer como tira de `<Button asChild><Link>` com `flex-wrap` — e 6 botões viram 3 linhas no
celular. Com 3+ seções a regra é a das abas: **`Select` abaixo de 768px que navega**, tira de
`<Link>` de verdade (middle-click, copiar link) acima. UM array de seções alimenta as duas formas;
a troca é CSS (`md:hidden` no trigger, `max-md:hidden` na `<nav>`).

```tsx
const SECTIONS = [
  { key: "config", label: "Configuração", to: "/orgs/$id/events/$eventId" },
  { key: "dashboard", label: "Dashboard", to: "/orgs/$id/events/$eventId/dashboard" },
  …
] as const;

<div>
  <Select value={activeKey} onValueChange={goToSection}>
    <SelectTrigger className="w-full md:hidden" aria-label="Seção do evento">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      {SECTIONS.map((s) => <SelectItem key={s.key} value={s.key}>{s.label}</SelectItem>)}
    </SelectContent>
  </Select>
  <nav aria-label="Seções do evento" className="flex flex-wrap items-center gap-2 max-md:hidden">
    {SECTIONS.map((s) => (
      <Button key={s.key} asChild size="sm" variant={s.key === activeKey ? "default" : "outline"}>
        <Link to={s.to} params={params}>{s.label}</Link>
      </Button>
    ))}
  </nav>
</div>
```

A chave do `Select` NUNCA é `""` (o Radix recusa `SelectItem value=""`) — a seção raiz ganha chave
própria (`config`). Envolva as duas formas num `<div>`: soltas como irmãs num `space-y-*`, a margem
cai no elemento escondido de um dos breakpoints. Canônico: `EventContextNav` do nexarena.

## PROIBIDO

- ❌ Tira de 3+ `<Button asChild><Link>` com `flex-wrap` e nada no mobile — empilha em várias linhas.
- ❌ **`isMobile ? <Select…> : <TabsList…>` no call site** — é o padrão que este componente
  substitui. Duplica a lista de abas, resolve em `useEffect` (flash + remount) e o próximo dev
  esquece de replicar. Se encontrar, **apague o ramo e deixe `<TabsList>` puro**.
- ❌ `overflow-x-auto` na tira "pra caber no mobile" — scroll horizontal de navegação esconde aba,
  não resolve.
- ❌ Duplicar a fonte de verdade das abas (um array pro Select, JSX pra tira).
- ❌ Passar `value={value}` (a prop crua) para o `TabsPrimitive.Root` — tem que ser `value={current}`.
  Ver item 1: com a prop crua o Select vira enfeite no call site não controlado.
- ❌ `mobile="strip"` como default por preguiça de conferir o rótulo em 375px.

## Auditoria

```bash
rg -n "isMobile \?" frontend/src --glob '!**/ui/sidebar.tsx'   # tabs/tabelas com switch em JS
rg -n "<TabsList" frontend/src --glob '!**/ui/**'              # confirmar que o dual-render cobre
rg -n 'Active \? "default" : "outline"' frontend/src           # tira de seções por rota sem Select
```

Achou `isMobile ? <Select` perto de um `TabsList`? → apagar o ramo mobile, deixar `<TabsList>`,
remover `useIsMobile` e os imports de `Select*` que ficarem órfãos (o `tsgo` acusa: `TS6133`/`TS6192`).
