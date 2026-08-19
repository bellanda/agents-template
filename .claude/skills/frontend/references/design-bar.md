# Barra Estética Mínima

> Reference do gate `frontend` (item 9 do checklist). O piso de qualidade visual que vale em TODA
> UI — sem virar exploração estética. Para escolher direção/paleta/fonte/estilo de uma tela com peso
> de marca (landing, hero, dashboard novo), abra a skill `ui-ux-pro-max` (base consultável de estilos,
> paletas e fontes) e comprometa-se com uma direção.

## O piso (sempre)

- **Sem cara genérica de IA.** NUNCA o combo clichê: gradiente roxo em fundo branco, `Inter`/`Roboto`/
  system font como escolha "de marca", layout previsível e simétrico sem intenção. Se parece template
  default, está errado.
- **Respeite a IDENTIDADE do projeto.** Font-family, cores (`--primary` hue, paleta) e estilo shadcn
  são da marca de CADA app — NUNCA unifique entre projetos. A consistência cross-projeto é de
  layout/largura/overlay (o gate), não de visual.
- **Hierarquia clara.** Um foco por tela. Tamanho/peso/cor guiam o olho na ordem certa (título →
  conteúdo → ação). Sem dois "heróis" competindo.
- **Contraste suficiente.** Texto sobre fundo ≥ AA. Estados (hover/active/disabled/focus) visíveis e
  distintos. Foco de teclado nunca removido sem substituto.
- **Espaçamento rítmico.** Escala consistente (multiplos de 4) para padding/gap/margin. Densidade
  proposital — respiro OU densidade controlada, não aleatório.
- **Semantic tokens.** Cores via vars shadcn (`bg-background`, `text-muted-foreground`), NUNCA hex
  cru. (Tokens/OKLCH → skill `tailwind-4-setup`.)

## Quando subir o nível (abrir `ui-ux-pro-max` + comprometer com direção)

Landing/hero, login flow, dashboard novo, qualquer tela com peso de marca. Aí vale tom extremo
(minimal brutal, editorial, retro-futurista, luxo refinado…), tipografia display distinta, motion
orquestrado de entrada, composição espacial com personalidade. Utility puro (table row, form input,
dropdown) NÃO precisa disso — usa shadcn e segue.
