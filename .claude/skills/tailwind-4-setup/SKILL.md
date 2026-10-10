---
name: tailwind-4-setup
description: Setup e operação de Tailwind CSS 4 — config CSS-first sem `tailwind.config.ts` em projeto greenfield, `@import "tailwindcss"` substituindo `@tailwind base/components/utilities` do v3, `@theme inline` para tokens OKLCH semantic compatíveis com shadcn (`--color-background`, `--color-foreground`, `--color-primary`, etc.), container queries (`@container/name` + `@sm:`/`@md:`) para tudo que adapta à LARGURA ÚTIL (wrapper do shell = `@container/main`), viewport breakpoints (`sm:`, `md:`, `lg:`) reservados para shell/sidebar/header, overlays e trocas mobile canônicas, mobile-first sempre. INVOCAR ANTES de — setup tailwind em projeto novo, criar/editar `index.css`/`globals.css`, configurar tema (cores, fontes, spacing), definir cor semantic shadcn, adicionar container query, migrar projeto Tailwind 3 → 4, decidir entre `@container` e viewport breakpoint, ou tocar `tailwind.config.ts` legado em projeto v3. NUNCA crie `tailwind.config.ts` em projeto novo greenfield; NUNCA `@tailwind base` (v3 syntax); NUNCA cor raw (`bg-blue-500`) — sempre semantic shadcn; NUNCA viewport breakpoint em componente que adapta ao container.
---

# Tailwind CSS 4 — CSS-First Setup

Tailwind 4 movimenta a config inteira para CSS. Em projeto novo, `tailwind.config.ts` **não existe**. Tokens, breakpoints, screens, font families, plugins — tudo em CSS via `@theme`.

## 1. Install + entry CSS

```bash
bun add -d tailwindcss @tailwindcss/vite
```

```ts
// vite.config.ts
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react(), tailwindcss()],
});
```

```css
/* src/index.css */
@import "tailwindcss";

@theme inline {
  /* tokens aqui */
}
```

Critical: `@import "tailwindcss"` substitui `@tailwind base;`/`@tailwind components;`/`@tailwind utilities;` do v3. Se você ainda escreve o trio, está em v3.

## 2. `@theme inline` — tokens OKLCH para shadcn

Shadcn/ui 4 usa CSS variables semantic. Defina-as em OKLCH (perceptualmente uniforme, fácil de derivar dark mode):

```css
@theme inline {
  /* Light mode (default) */
  --color-background: oklch(1 0 0);
  --color-foreground: oklch(0.145 0 0);
  --color-card: oklch(1 0 0);
  --color-card-foreground: oklch(0.145 0 0);
  --color-popover: oklch(1 0 0);
  --color-popover-foreground: oklch(0.145 0 0);
  --color-primary: oklch(0.205 0 0);
  --color-primary-foreground: oklch(0.985 0 0);
  --color-secondary: oklch(0.97 0 0);
  --color-secondary-foreground: oklch(0.205 0 0);
  --color-muted: oklch(0.97 0 0);
  --color-muted-foreground: oklch(0.556 0 0);
  --color-accent: oklch(0.97 0 0);
  --color-accent-foreground: oklch(0.205 0 0);
  --color-destructive: oklch(0.577 0.245 27.325);
  --color-destructive-foreground: oklch(0.985 0 0);
  --color-border: oklch(0.922 0 0);
  --color-input: oklch(0.922 0 0);
  --color-ring: oklch(0.708 0 0);

  /* Radius */
  --radius: 0.625rem;

  /* Container queries enabled by default em v4 */
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
  @theme inline {
    --color-background: oklch(0.145 0 0);
    --color-foreground: oklch(0.985 0 0);
    /* ... */
  }
}

/* Ou class-based: */
.dark {
  --color-background: oklch(0.145 0 0);
  --color-foreground: oklch(0.985 0 0);
  /* ... */
}
```

Esses tokens viram utilities automaticamente: `bg-background`, `text-foreground`, `border-border`, `ring-ring`, etc.

## 3. OKLCH cheatsheet

Format: `oklch(L C H)` onde:
- **L** = lightness 0..1 (0 = preto, 1 = branco)
- **C** = chroma 0..0.4 (0 = neutro grayscale, > 0.2 = saturado)
- **H** = hue 0..360 (0=red, 120=green, 240=blue)

Grayscale: chroma 0 e hue 0. Lightness varia. Ex: `oklch(0.205 0 0)` = cinza escuro.

Vantagens vs HSL:
- Perceptualmente uniforme: `oklch(0.5 ...)` é igual de claro pra qualquer hue.
- Dark mode trivial: inverte L (`0.205` → `0.985`), mantém C e H.
- Suporte nativo em browsers modernos (2023+).

## 4. Container queries — DEFAULT para layout de página E componentes

Largura útil ≠ viewport: com a sidebar aberta (~256px) um notebook de 1024–1440 tem ~700–1100px úteis, e `lg:`/`xl:` disparam cedo demais (valores cortados, abas sobrepostas). Decisão 2026-10-09: o wrapper de conteúdo do shell declara `@container/main` e o layout DENTRO da página responde a ele. Viewport (`sm:`, `md:`, `lg:`) fica só para shell/sidebar/header, overlays (são `fixed`) e as trocas mobile canônicas (DataList tabela↔card, filtros↔dialog).

```tsx
{/* Shell: wrapper de conteúdo */}
<div className="@container/main mx-auto w-full max-w-[1440px]">…</div>

{/* Página: responde à largura útil. Mapa: sm→@xl/main · md→@2xl/main · lg→@4xl/main · xl→@6xl/main */}
<div className="grid grid-cols-1 gap-4 @xl/main:grid-cols-2 @4xl/main:grid-cols-3">…</div>

{/* Componente reusável (aparece em dialog, coluna, página): @container próprio, sem nome */}
<Card className="@container"><p className="text-xl @[12rem]:text-2xl">…</p></Card>

{/* Shell: sidebar adapta à viewport (ok) */}
<div className="grid grid-cols-1 lg:grid-cols-[240px_1fr]">…</div>
```

Sintaxe (Tailwind 4.3): `@container/<nome>` (pai), `@xl/main:` (min-width do container nomeado), `@max-[38rem]/tabs:` (largura < 38rem), `@[12rem]:` (valor arbitrário). Sem nome = container mais próximo. Container com `inline-size` não deixa o filho definir a largura: o pai precisa de `w-full`/`min-w-0`/`flex-1`.

## 5. Mobile-first é obrigatório

Base styles para mobile (sem prefix), scale up com `sm:` → `md:` → `lg:` → `xl:` → `2xl:`.

```tsx
{/* GOOD: mobile-first */}
<div className="text-sm md:text-base lg:text-lg">

{/* BAD: desktop-first com max-width */}
<div className="text-lg max-md:text-sm">
```

Inverter a direção (desktop-first) torna o código frágil — toda variação de design tem que ser pensada em "subtraindo" do desktop.

## 6. Semantic CSS variables — NUNCA raw colors

```tsx
{/* GOOD: semantic, theme-aware */}
<div className="bg-background text-foreground border-border">
<Button variant="destructive">  {/* usa --color-destructive */}

{/* BAD: raw, quebra com theme switch */}
<div className="bg-white text-zinc-900 border-zinc-200">
<button className="bg-red-500 text-white">
```

Por que: o sistema shadcn troca apenas as variables (light↔dark, ou theming customizado por client). Raw colors hardcoded ignoram o theme.

## 7. Plugins via CSS

Plugins comuns (typography, forms, container-queries) integrados como CSS imports:

```css
@import "tailwindcss";
@plugin "@tailwindcss/typography";
@plugin "@tailwindcss/forms";
```

Sem `tailwind.config.ts`. Sem `plugins: [require(...)]`.

## 8. Quando MANTER `tailwind.config.ts`

Só em projeto **legado v3 que tem plugin v3 sem equivalente v4**. Greenfield em 2026 = CSS-only.

Se o projeto é v3 e você quer migrar para v4:

1. `bun remove tailwindcss postcss autoprefixer` (toolchain v3).
2. `bun add -d tailwindcss @tailwindcss/vite` (v4).
3. Configurar vite plugin (passo 1 acima).
4. Substituir `@tailwind base/components/utilities` por `@import "tailwindcss"`.
5. Mover tokens do `tailwind.config.ts > theme.extend.colors` para `@theme inline`.
6. Deletar `tailwind.config.ts` + `postcss.config.js`.
7. Trocar plugins JS por `@plugin "..."` CSS.
8. Smoke test todas rotas — `oklch()` requer browser moderno.

## 9. Setup completo (template `index.css`)

```css
@import "tailwindcss";

@theme inline {
  /* shadcn light tokens */
  --color-background: oklch(1 0 0);
  --color-foreground: oklch(0.145 0 0);
  --color-card: oklch(1 0 0);
  --color-card-foreground: oklch(0.145 0 0);
  --color-popover: oklch(1 0 0);
  --color-popover-foreground: oklch(0.145 0 0);
  --color-primary: oklch(0.205 0 0);
  --color-primary-foreground: oklch(0.985 0 0);
  --color-secondary: oklch(0.97 0 0);
  --color-secondary-foreground: oklch(0.205 0 0);
  --color-muted: oklch(0.97 0 0);
  --color-muted-foreground: oklch(0.556 0 0);
  --color-accent: oklch(0.97 0 0);
  --color-accent-foreground: oklch(0.205 0 0);
  --color-destructive: oklch(0.577 0.245 27.325);
  --color-destructive-foreground: oklch(0.985 0 0);
  --color-border: oklch(0.922 0 0);
  --color-input: oklch(0.922 0 0);
  --color-ring: oklch(0.708 0 0);

  /* Charts (shadcn charts) */
  --color-chart-1: oklch(0.646 0.222 41.116);
  --color-chart-2: oklch(0.6 0.118 184.704);
  --color-chart-3: oklch(0.398 0.07 227.392);
  --color-chart-4: oklch(0.828 0.189 84.429);
  --color-chart-5: oklch(0.769 0.188 70.08);

  --radius: 0.625rem;
}

.dark {
  --color-background: oklch(0.145 0 0);
  --color-foreground: oklch(0.985 0 0);
  --color-card: oklch(0.205 0 0);
  --color-card-foreground: oklch(0.985 0 0);
  --color-popover: oklch(0.205 0 0);
  --color-popover-foreground: oklch(0.985 0 0);
  --color-primary: oklch(0.922 0 0);
  --color-primary-foreground: oklch(0.205 0 0);
  --color-secondary: oklch(0.269 0 0);
  --color-secondary-foreground: oklch(0.985 0 0);
  --color-muted: oklch(0.269 0 0);
  --color-muted-foreground: oklch(0.708 0 0);
  --color-accent: oklch(0.269 0 0);
  --color-accent-foreground: oklch(0.985 0 0);
  --color-destructive: oklch(0.704 0.191 22.216);
  --color-destructive-foreground: oklch(0.985 0 0);
  --color-border: oklch(1 0 0 / 10%);
  --color-input: oklch(1 0 0 / 15%);
  --color-ring: oklch(0.556 0 0);
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
```

## Don'ts

- **NUNCA** crie `tailwind.config.ts` em projeto greenfield.
- **NUNCA** `@tailwind base; @tailwind components; @tailwind utilities;` (v3 syntax).
- **NUNCA** raw colors em componente (`bg-blue-500`, `text-zinc-900`) — sempre semantic shadcn.
- **NUNCA** desktop-first (`max-md:` para esconder no mobile) — sempre mobile-first com scale up.
- **NUNCA** viewport breakpoint (`md:`/`lg:`) em grid/flex de página ou componente reusável — use `@container` (`@…/main:` na página). Viewport só p/ shell, overlays e trocas mobile canônicas.
- **NUNCA** HSL/HEX para tokens novos — use OKLCH (browser support ok desde 2023).
- **NUNCA** plugin via `tailwind.config.ts > plugins:` em v4 — use `@plugin "..."` em CSS.
