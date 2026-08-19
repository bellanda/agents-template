# Grid vs Stack — quando quebrar linha mesmo no desktop

A pergunta NÃO é "mobile ou desktop". É **a natureza do conteúdo**. Decida primeiro se os itens
são _paralelos_ (peers, independentes) ou _sequenciais_ (dependentes, lidos em ordem).

## Peers (independentes) → GRID

Cards de eventos, KPIs, métricas, campos sem relação de ordem entre si. Escalam em colunas
conforme a largura. Mobile 1, sobe com breakpoints.

```tsx
// cards / itens de lista
<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">{items}</div>

// KPIs compactos podem adensar mais
<div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">{kpis}</div>

// par de campos independentes (cidade / estado)
<div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
  <Field label="Cidade" />
  <Field label="Estado" />
</div>
```

Tudo dentro do cap do layout (1440) — não esparrama em ultrawide.

## Sequencial (dependentes) → 1 COLUNA, mesmo no desktop

Conteúdo lido de cima pra baixo como uma sequência. Colocar lado a lado quebra a lógica visual e
fica feio. **Mantenha 1 coluna em qualquer tela** e **contenha a largura do GRUPO** (no fieldgroup,
nunca na página).

Casos clássicos:

- **Intervalos de data**: início → data do evento → encerramento. São dependentes (um vem depois
  do outro no tempo). 1 por linha, mesmo em xl.
- **Logo → Banner**: ordem + aspect ratios diferentes. Empilhado full-width (ver abaixo).
- **Passos / etapas ordenadas**, **endereço** (logradouro → número → complemento), qualquer
  "preencha nesta ordem".

```tsx
// datas dependentes — 1 coluna contida, NUNCA grid lado a lado
<div className="flex max-w-2xl flex-col gap-4">
  <Field label="Início das inscrições" type="datetime-local" />
  <Field label="Data do evento" type="datetime-local" />
  <Field label="Encerramento" type="datetime-local" />
</div>
```

A largura curta (`max-w-2xl`) vai no **grupo/form**, deixando a página inteira na largura do layout.

## Logo + Banner → empilhado full-width

Anti-padrão real (deixa o banner minúsculo e o logo proporcionalmente gigante):

```tsx
// ERRADO — colunas iguais; banner 16:9 espremido em metade da largura
<div className="grid gap-4 sm:grid-cols-2">
  <AssetSlot aspect="aspect-square" /> {/* logo */}
  <AssetSlot aspect="aspect-video" /> {/* banner espremido */}
</div>
```

Certo — empilhado, cada um full-width, preview no aspect ratio real:

```tsx
<div className="flex max-w-2xl flex-col gap-6">
  <AssetSlot label="Logo" aspect="aspect-square" className="w-40" />{" "}
  {/* logo contido */}
  <AssetSlot label="Banner" aspect="aspect-video" className="w-full" />{" "}
  {/* banner full-width */}
</div>
```

## Regra de bolso

> Consigo trocar a ordem dos itens sem perder sentido? → **peers → grid**.
> A ordem importa / um depende do outro? → **sequencial → 1 coluna contida**.
