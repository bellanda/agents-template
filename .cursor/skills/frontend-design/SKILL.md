---
name: frontend-design
description: Distinctive, production-grade frontend interfaces that avoid generic AI aesthetics. Invoque ANTES de criar UI com peso estético/de marca — landing pages, hero sections, dashboards novos, login flows, componentes com personalidade visual. NÃO use para utility components puros (table row, form input wrapper, dropdown) — para esses use a skill `shadcn`.
---

# Frontend Design — Distinctive, Production-Grade UI

Guide for creating frontend interfaces with exceptional aesthetic quality and creative intentionality — avoiding generic "AI slop". Covers design thinking (purpose/tone/differentiation), aesthetics (typography, color, motion, spatial composition), and concrete implementation patterns.

## Design Thinking

Before coding, understand the context and commit to a BOLD aesthetic direction:

- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick an extreme: brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian, etc. There are so many flavors to choose from. Use these for inspiration but design one that is true to the aesthetic direction.
- **Constraints**: Technical requirements (framework, performance, accessibility).
- **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember?

**CRITICAL**: Choose a clear conceptual direction and execute it with precision. Bold maximalism and refined minimalism both work - the key is intentionality, not intensity.

Then implement working code (HTML/CSS/JS, React, Vue, etc.) that is:

- Production-grade and functional
- Visually striking and memorable
- Cohesive with a clear aesthetic point-of-view
- Meticulously refined in every detail

## Frontend Aesthetics Guidelines

Focus on:

- **Typography**: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics; unexpected, characterful font choices. Pair a distinctive display font with a refined body font.
- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes.
- **Motion**: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions. Use scroll-triggering and hover states that surprise.
- **Spatial Composition**: Unexpected layouts. Asymmetry. Overlap. Diagonal flow. Grid-breaking elements. Generous negative space OR controlled density.
- **Backgrounds & Visual Details**: Create atmosphere and depth rather than defaulting to solid colors. Add contextual effects and textures that match the overall aesthetic. Apply creative forms like gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, and grain overlays.

NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts), cliched color schemes (particularly purple gradients on white backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character.

Interpret creatively and make unexpected choices that feel genuinely designed for the context. No design should be the same. Vary between light and dark themes, different fonts, different aesthetics. NEVER converge on common choices (Space Grotesk, for example) across generations.

**IMPORTANT**: Match implementation complexity to the aesthetic vision. Maximalist designs need elaborate code with extensive animations and effects. Minimalist or refined designs need restraint, precision, and careful attention to spacing, typography, and subtle details. Elegance comes from executing the vision well.

Remember: Claude is capable of extraordinary creative work. Don't hold back, show what can truly be created when thinking outside the box and committing fully to a distinctive vision.

## Stack-Specific Component Sources

Quando for implementar, escolha o nível de "vida" pelo papel do componente:

| Papel                                                          | Source                                                        |
| -------------------------------------------------------------- | ------------------------------------------------------------- |
| Utility (input, dropdown, dialog, form, table, command palette)| **Shadcn/ui** registry oficial                                |
| "Com personalidade" (CTA, hero number, marquee, animated list, KPI tickado, BorderBeam) | **Magic UI** — extende Shadcn. Ver skill `shadcn > rules/magic-ui.md` |
| Visual 3D / shaders / scene interativa                         | **Three.js + React Three Fiber (`@react-three/fiber`) + drei**. Referência expandida em skill `ui-ux-pro-max > data/stacks/threejs.csv` |
| Animação 2D (page entrance, micro-interactions complexos)      | **Motion** (lib `motion`, não framer-motion legado)           |
| Charts / data viz                                              | **Shadcn Charts** (wrap Recharts). Ver `shadcn > rules/charts.md` |

Mantém a regra: **direção estética > biblioteca**. Magic UI e Three.js servem a uma visão estética escolhida — não invente uso só pra "ter feature".
