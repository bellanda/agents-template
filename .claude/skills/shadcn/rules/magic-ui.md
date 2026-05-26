# Magic UI — Componentes "com Personalidade"

Magic UI **estende** o registry shadcn. Mesma stack (Tailwind 4, Radix base, CSS vars semantic, `cn()` helper), mesma CLI (`bunx shadcn@latest add @magicui/...`). Não é UI framework concorrente; é catálogo de componentes pra adicionar "vida visual" onde shadcn deixa neutro.

## Quando usar

- Landing page: hero com `<Globe>`, KPI com `<NumberTicker>`, social proof com `<Marquee>`.
- Dashboard: `<AnimatedBeam>` conectando cards, `<BorderBeam>` em card de upgrade, `<Particles>` em background.
- CTA / botão de destaque: `<ShimmerButton>`, `<RainbowButton>`, `<PulsatingButton>`.
- Notificação / toast: `<AnimatedList>` para feed de eventos.
- Component "wow": `<TextReveal>`, `<TypingAnimation>`, `<HyperText>`, `<MorphingText>`.

**Não usar para utility puro** — table row, dropdown, input. Esses ficam em shadcn base.

## Instalação

```bash
# Em projeto Vite SPA com bun
bunx shadcn@latest add @magicui/shimmer-button
bunx shadcn@latest add @magicui/animated-list
bunx shadcn@latest add @magicui/globe @magicui/number-ticker @magicui/marquee
```

Após `add`, ler o arquivo gerado e corrigir:

1. **Imports do registry usam paths default (`@/components/ui/...`)** — se o projeto tem `aliases` diferentes em `components.json`, reescreva os imports manualmente. A CLI rewrite só os arquivos UI próprios; arquivos co-instalados não.
2. **Icon library** — Magic UI vem importando `lucide-react` por default. Se o projeto usa `hugeicons` ou `@tabler/icons-react`, trocar.
3. **`cn()` import path** — checar se aponta pro `@/lib/utils` do projeto.

## Componentes que valem a pena (curadoria)

| Componente               | Bom para                                                                   |
| ------------------------ | -------------------------------------------------------------------------- |
| `<AnimatedList>`         | Feed de notificações, atividade recente, eventos de webhook                |
| `<NumberTicker>`         | KPI animado (revenue, users, deals)                                        |
| `<Marquee>`              | Logos de clientes, depoimentos rolando, mensagens em loop                  |
| `<Globe>`                | Cobertura geográfica, "clientes no mundo todo"                             |
| `<AnimatedBeam>`         | Diagrama de integração (cards conectados por beam animado)                 |
| `<BorderBeam>`           | Card de plano premium, CTA de upgrade                                      |
| `<ShimmerButton>`        | CTA principal de landing                                                   |
| `<TextReveal>`           | Hero com texto se revelando ao scroll                                      |
| `<TypingAnimation>`      | Chat/AI demo, hero técnico                                                 |
| `<Particles>`            | Background sutil (densidade baixa, opacity baixa)                          |
| `<DotPattern>`           | Background neutro (substitui CSS pattern manual)                           |
| `<MagicCard>`            | Card com efeito de luz seguindo o mouse                                    |

## Performance caveats

Magic UI usa **animação CSS + Motion + canvas** dependendo do componente. Caveats por categoria:

- **Componentes canvas (`<Globe>`, `<Particles>`, `<Meteors>`):** custosos em paint. Limitar a **1 por viewport visível**. Usar `<Suspense>` + lazy import se for abaixo da fold. Em mobile, considerar desativar via media query.
- **Componentes Motion (`<Marquee>`, `<AnimatedList>`, `<TextReveal>`):** baratos. Cuidar de `key` estável em items de `<AnimatedList>` — sem isso, re-mount a cada update.
- **Hover-driven (`<MagicCard>`, `<BorderBeam>`):** custo de mousemove listener. OK em até ~10 cards por viewport; muito mais que isso, virar opt-in via `whileInView`.
- **Recharts overlap:** se a página tem chart Recharts + componente canvas Magic UI, monitorar `chart:mount/unmount` delta (ver skill `frontend-performance-ultimate`). Componente canvas pode invalidar memoization upstream.

## Quando NÃO usar Magic UI

- Background de form de admin — neutro é melhor que "vivo". Magic UI quer atenção.
- Tabela de dados densa — distração.
- Loop com 50+ items animados — vai derrubar FPS. Usar `<Marquee>` com `repeat={4}` em vez de listar 200 items.
- Já tem skill `frontend-design` recomendando aesthetic diferente (brutalist, minimal extremo) — Magic UI é "tech polished" por default, pode bater com a direção estética escolhida.

## Convivência com Shadcn base

Magic UI **não substitui** Shadcn base. Forms, tables, dialogs, command palette continuam vindo do shadcn registry oficial. Magic UI entra em **CTAs, hero, marketing, feed visual, KPI dashboard**.

Regra prática: se o componente tem função utilitária (form input, dropdown, dialog), shadcn base. Se a função do componente é **causar reação emocional** (CTA, hero number, "olha que legal"), Magic UI vale.
