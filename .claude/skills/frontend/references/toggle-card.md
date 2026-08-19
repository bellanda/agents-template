# ToggleCard — toggle boolean como card clicável

> Reference do gate `frontend` (item 8a do checklist). Abra ANTES de colocar qualquer `Switch`
> perto de um rótulo/card. Fonte canônica do componente: `references/toggle-card.tsx` (vendored
> por projeto em `components/ui/toggle-card.tsx`).

**Princípio:** Switch pequeno dentro de card largo é anti-padrão — em desktop o `justify-between`
empurra o tick para longe do rótulo e o touch target fica ínfimo. O card INTEIRO é o controle:
estado lê-se pelo chip ("Ativo"/"Desativado") + **liquid wash** (faixas estreitas de luz varrendo
o card — entram, atravessam ~1/3 por vez e somem, dando sensação de passagem) + um **hairline
border beam** (0.5px) orbitando a borda **sincronizado** ao wash (1 volta a cada 2 ciclos da onda;
brilho pulsa junto), nunca por um tick distante. OFF tem contraste forte: card bem cinza e apagado
(`border-border/70 bg-muted/50`), sem animação.

## Tabela de decisão

| Cenário                                                            | Use                                       |
| ------------------------------------------------------------------ | ----------------------------------------- |
| Feature flag, habilitar módulo, qualquer on/off com rótulo         | **ToggleCard** (`size="default"`)         |
| Peers independentes (Diário/Semanal/Mensal, dias, planos)          | **ToggleCard** `size="compact"` em grid   |
| Multi-select ("inclua estes itens"), semântica de seleção          | `CardCheckbox` (coexiste; é checkbox)     |
| Célula de tabela densa onde a LINHA já é o rótulo                  | Switch inline residual (**única exceção**) |

**Regra de eliminação do Switch:** o Switch sobrevive SOMENTE em célula de tabela densa sem
superfície para card (ex.: coluna "Ativo" numa tabela de 8 colunas). Todo outro contexto com
rótulo visível → ToggleCard.

## Largura (anti "card esticado")

- Peers → `grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3` (item 3 do gate).
- ToggleCard único em fluxo sequencial → **grupo contido** (`max-w-lg` no fieldgroup, NUNCA na
  página). Card de toggle nunca estica full-width em desktop.

## Padrão TSX canônico

```tsx
// Peers em grid (Diário/Semanal/Mensal, planos, tiers)
<div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
  <ToggleCard size="compact" checked={daily} onCheckedChange={setDaily} title="Diário" />
  <ToggleCard size="compact" checked={weekly} onCheckedChange={setWeekly} title="Semanal" />
  <ToggleCard size="compact" checked={monthly} onCheckedChange={setMonthly} title="Mensal" />
</div>

// Toggle único — grupo contido, description dinâmica por estado.
// ATENÇÃO: pending/saving transitório vai em `busy` (bloqueia clique SEM dim e
// SEM reiniciar o beam). `disabled` é só para card permanentemente inativo —
// `disabled={isPending}` faz TODOS os cards da tela piscarem quando um salva.
<div className="max-w-lg">
  <ToggleCard
    checked={config.enabled}
    onCheckedChange={(enabled) => onUpdate({ enabled })}
    title="Agendamento automático"
    description={
      config.enabled
        ? "Relatórios são gerados automaticamente."
        : "Nenhum relatório automático é gerado."
    }
    busy={saving}
  />
</div>

// Labels customizados (binário não-Ativo/Desativado) e accent crítico
<ToggleCard
  checked={open}
  onCheckedChange={setOpen}
  title="Segunda-feira"
  size="compact"
  activeLabel="Aberto"
  inactiveLabel="Fechado"
/>
<ToggleCard checked={x} onCheckedChange={setX} title="..." accent="destructive" />
```

## CSS — keyframes no global (`index.css` / `globals.css` de cada projeto)

Tailwind 4 CSS-first: tokens `--animate-*` + `@keyframes` dentro de `@theme` geram as utilities
`animate-tc-*`. O **wash** são duas faixas borradas (`w-[45%]`/`w-[50%]` `blur-2xl`) que varrem na
horizontal via `transform` + `opacity` (entram, atravessam, somem). O **beam** é um span gradiente
hairline (`h-[0.5px] w-14`) orbitando a borda via `offset-path: rect(... round var(--radius))` +
`offset-distance` 0→100% (técnica do Border Beam do MagicUI, sem dependência `motion`); travel e
brilho são animações separadas (`tc-beam-travel` 6s + `tc-beam-pulse` 3s) pra travar 1 volta a cada
2 ciclos do wash. NUNCA anime `background-image`/gradiente em keyframe (browsers não interpolam —
"pula" entre frames); só `transform`/`opacity` (wash, dot) e `offset-distance` (beam). Reduced-motion:
wash e beam usam `motion-reduce:hidden` (parados seriam manchas/risco visíveis); o dot usa
`motion-reduce:animate-none`.

```css
/* ToggleCard (gate frontend, ref toggle-card.md) — liquid wash + synced border beam + status dot */
@theme {
  --animate-tc-beam: tc-beam-travel 6s linear infinite, tc-beam-pulse 3s ease-in-out infinite;
  --animate-tc-wash-a: tc-wash-a 3s ease-in-out infinite;
  --animate-tc-wash-b: tc-wash-b 4s ease-in-out infinite;
  --animate-tc-dot: tc-dot 2.4s cubic-bezier(0.4, 0, 0.6, 1) infinite;

  /* sweep-across: faixa estreita atravessa o card (~1/3 aceso por vez) → sai e some → reset invisível.
     translate em % é relativo à largura da faixa (≈45% do card), então X grande = travessia completa. */
  @keyframes tc-wash-a {
    0%,
    100% {
      transform: translate(0, 0) scale(1);
      opacity: 0;
    }
    15% {
      opacity: 1;
    }
    50% {
      transform: translate(150%, 8%) scale(1.1);
      opacity: 0.85;
    }
    72% {
      transform: translate(270%, 14%) scale(1);
      opacity: 0;
    }
  }
  @keyframes tc-wash-b {
    0%,
    100% {
      transform: translate(0, 0) scale(1);
      opacity: 0;
    }
    20% {
      opacity: 0.85;
    }
    55% {
      transform: translate(-150%, -8%) scale(1.1);
      opacity: 0.6;
    }
    78% {
      transform: translate(-270%, -12%) scale(1);
      opacity: 0;
    }
  }
  /* border beam: 1 volta (6s) enquanto o wash-a faz 2 ciclos (3s). Travel e brilho separados —
     travel contínuo 0→100% (seam coincide no path fechado); brilho pulsa a cada 3s, sincronizado
     a cada passada da onda (sobe a 15%, baixa a 72% quando o card esvazia). */
  @keyframes tc-beam-travel {
    from {
      offset-distance: 0%;
    }
    to {
      offset-distance: 100%;
    }
  }
  @keyframes tc-beam-pulse {
    0%,
    100% {
      opacity: 0.35;
    }
    15% {
      opacity: 1;
    }
    50% {
      opacity: 0.85;
    }
    72% {
      opacity: 0.35;
    }
  }
  @keyframes tc-dot {
    0%,
    100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.55;
      transform: scale(0.75);
    }
  }
}
```

## Don'ts

- **NUNCA** pending/saving transitório em `disabled` — é `busy`. `disabled` aplica `opacity-50` e
  desliga o wash/beam; quando um save flipa `disabled` de todos os cards da tela, TODOS piscam.
- **NUNCA** `max-w` na página por causa de um ToggleCard — contenha no fieldgroup (`max-w-lg`).
- **NUNCA** ToggleCard `size="default"` dentro de tabela densa — célula de tabela é a exceção do
  Switch inline.
- **NUNCA** ToggleCard para multi-select ("selecione vários") — é `CardCheckbox`.
- **NUNCA** Switch visível dentro do ToggleCard — o card inteiro JÁ é o controle.
- **NUNCA** dependência de `motion` no ToggleCard — animação é CSS-only (projetos sem `motion`,
  ex. lakehouse-hpe, usam o mesmo componente).
- **NUNCA** anime `background`/gradiente nos keyframes — só `transform`/`opacity` (wash, dot) e
  `offset-distance` (beam).
- **NUNCA** esqueça os keyframes ao vendorar o componente num projeto novo — sem eles o wash não
  anima e o beam não dá a volta (sem erro de build; só "fica parado").
