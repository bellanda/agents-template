---
name: epic-startup-landing
description: The standard "epic startup" entry/landing screen for a React + TanStack Router app — a public, full-screen route (no app shell) with a magic-ui Particles background, a large product wordmark, a one-line subtitle, and a single CTA that routes to /login. Use when building the initial landing/entry page, a hero screen, or a pre-login splash. Triggers on "landing", "tela inicial", "página inicial", "startup épica", "hero com particles", "splash screen". Pairs with `frontend-design` (aesthetic direction) and `shadcn` (installs the Particles component); the authenticated side is the `standard-app-shell` skill.
---

# Epic Startup Landing

The canonical public entry screen: a full-screen, atmospheric route at `/` that exists to do one thing — get the visitor to `/login`. It is **not** inside the app shell.

This skill fixes the **structure and contract** (route, layering, single CTA → login). The **aesthetic direction** — palette, exact typography treatment, motion intensity — comes from the `frontend-design` skill; invoke it alongside this one and commit to a bold, context-specific direction rather than a generic hero.

## Contract

| Rule | Detail |
| --- | --- |
| **Public, no shell** | Lives at `src/routes/index.tsx`, a direct child of the bare `__root.tsx`. No sidebar, no header. |
| **Redirect authed users** | `beforeLoad` → if `useAuthStore.getState().accessToken`, `throw redirect({ to: "/app/dashboard" })`. A logged-in user never sees the landing. |
| **One CTA** | A single primary `<Button asChild>` wrapping `<Link to="/login">`. No secondary actions competing with it. |
| **Full-screen** | `relative min-h-screen w-full overflow-hidden`. `overflow-hidden` so the glow/particles never spawn scrollbars. |

## Layered composition (back to front)

1. **Base** — solid background. For a dark scene, scope it: `<div className="dark ... bg-background">` so the `.dark` CSS vars apply locally even in a light-themed app.
2. **Particles** — magic-ui `<Particles className="absolute inset-0 z-0" />`. `color` must contrast the base (`#ffffff` on dark). `quantity` ~120–160; tune `ease`/`staticity` for drift feel.
3. **Radial glow** — one soft `radial-gradient` blob behind the wordmark (`blur-3xl`, low opacity) for depth. Use `color-mix(in oklch, var(--foreground) ~13%, transparent)`.
4. **Vignette** — `radial-gradient(ellipse at center, transparent ~40%, var(--background) 100%)` over `inset-0` to pull focus inward.
5. **Content** — `relative z-10`, centered column: eyebrow → wordmark → subtitle → CTA.

All decorative layers get `aria-hidden` and `pointer-events-none`.

## Content stack

- **Eyebrow** — small, uppercase, wide-tracked, muted label. A good spot for a tiny product-specific signature detail (e.g. a small motif drawn from the product's brand).
- **Wordmark** — the product name, very large (`text-6xl` → `text-8xl`), `font-bold tracking-tight`. Make it distinctive through scale, tracking, and one accent treatment (e.g. a `bg-linear-to-r ... bg-clip-text text-transparent` gradient on part of the name) — not a second font unless the project's design system has one.
- **Subtitle** — exactly one line, `text-balance`, muted, says what the product is. UI strings in the project's locale (pt-BR here).
- **CTA** — `<Button size="lg" asChild>` + `<Link to="/login">` + a trailing `ArrowRight` with `data-icon="inline-end"`.

## Entrance motion

One orchestrated page-load reveal beats scattered micro-interactions. Stagger the four content elements with `tw-animate-css` (`animate-in fade-in-0 slide-in-from-bottom-3 duration-700 fill-mode-both`) and an explicit per-element `style={{ animationDelay }}` (0 / 100 / 200 / 300 ms). Inline `animationDelay` is used because Tailwind's `delay-*` targets `transition-delay`, not `animation-delay`.

## Setup

1. Invoke the **`shadcn`** skill → add Particles: `bunx shadcn@latest add "https://magicui.design/r/particles"`. Review the added file — magic-ui's `particles.tsx` uses `NodeJS.Timeout`; in a browser-only project change it to `ReturnType<typeof setTimeout>`.
2. Invoke **`frontend-design`** and commit to an aesthetic direction for the scene.
3. Copy `references/landing-route.tsx` to `src/routes/index.tsx`; adapt wordmark, subtitle, accent colors, eyebrow signature.
4. Verify: `/` renders full-screen with no shell; the CTA reaches `/login`; an authenticated visitor is redirected to `/app/dashboard`.

## References

- `references/landing-route.tsx` — the full landing route template (from the reference frontend).
