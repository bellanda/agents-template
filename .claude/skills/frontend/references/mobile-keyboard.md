# Teclado virtual, visual viewport e safe-area

> Reference do gate `frontend` (item 8e). Por que dialog alto some atrás do teclado no celular, e o
> componente canônico que resolve. Implementação: `references/form-dialog.tsx` (vendorado em
> `ui/form-dialog.tsx`).

## As duas viewports

| | O que é | Quem depende dela |
| --- | --- | --- |
| **Layout viewport** | Retângulo contra o qual o CSS resolve | `position: fixed`, `100vh`/`100dvh`/`svh`, `window.innerHeight` |
| **Visual viewport** | Os pixels realmente na tela | `window.visualViewport.{height, offsetTop, scale}` |

## Por que `dvh` NÃO resolve

**No iOS o teclado não encolhe a layout viewport.** `window.innerHeight` não muda; `100vh`,
`100dvh` e `100svh` continuam iguais. `dvh` acompanha o *chrome dinâmico do browser* (barra de
endereço colapsando), não o teclado — e em PWA standalone nem isso, porque não existe barra de
endereço (`100vh == 100dvh == 100svh == 100lvh`).

O que muda é `visualViewport.height`, que encolhe exatamente a altura do teclado.

**E tem um segundo efeito, que é o que de fato quebra o Radix.** Ao focar um campo que ficaria sob o
teclado, o WebKit traz o campo pra vista. Com o body travado pelo `react-remove-scroll` (todo Dialog
do Radix trava), o documento não pode rolar — então o WebKit desliza a *área visível* pra baixo dentro
da layout viewport, e `visualViewport.offsetTop` fica > 0. Como o `DialogContent` é `position: fixed`,
ele fica colado na layout viewport e **sobe pra fora da tela pelo topo**.

Conclusão: nenhum ajuste de `vh`/`dvh`/`svh`/`max-h` corrige isso. Só compensar o `offsetTop`.

## A tabela que justifica uma fórmula só

`keyboardInset = max(0, window.innerHeight − visualViewport.height)`

| Modo | `innerHeight` | `vv.height` | `keyboardInset` | `vv.offsetTop` |
| --- | --- | --- | --- | --- |
| iOS (Safari ou standalone) | inalterado | −teclado | = teclado | **> 0** ao focar |
| Android `interactive-widget=resizes-visual` | inalterado | −teclado | = teclado | 0 |
| Android `interactive-widget=resizes-content` | −teclado | −teclado | **0** (correto: a layout viewport já exclui) | 0 |

Por isso `top: var(--vv-offset-top); height: var(--vv-height)` está certo em **todas** as linhas —
sem branch de plataforma e sem risco de compensar duas vezes.

`interactive-widget` é honrado por Chromium/Firefox no Android. **O iOS ignora.** Não construa nada
que dependa dele; ele só serve pra ter o primeiro frame correto no Android antes de qualquer JS rodar.

## Meta viewport canônica (todos os projetos)

```html
<meta name="viewport"
      content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content" />
```

| Token | O que compra |
| --- | --- |
| `viewport-fit=cover` | **Obrigatório** pra `env(safe-area-inset-*)` retornar algo ≠ 0 no iOS. Sem ele o padding do footer é no-op |
| `interactive-widget=resizes-content` | Android encolhe a layout viewport sozinho. Ignorado em outros lugares (chave desconhecida é descartada) |

**Deliberadamente ausentes:** `maximum-scale=1` / `user-scalable=no` — violam WCAG 1.4.4 e o iOS os
ignora desde o iOS 10. O anti-zoom correto é a fonte do campo (seção abaixo).

### O campo precisa de ≥16px no celular — senão o iOS dá auto-zoom e joga o dialog pra fora

O gatilho é a fonte **computada do próprio campo**, não a do `<html>`. `html { font-size: 17px }`
NÃO cobre: `text-sm` = 0.875 × 17 = **14.875px**, `text-xs` = **12.75px** — ambos abaixo do limiar.

Focar um `<input>`/`<textarea>`/`<select>` nativo com fonte < 16px faz o Safari **dar zoom**. Zoomado,
a visual viewport encolhe e pana, e todo `position: fixed` — o dialog inteiro — some **pra cima e pra
esquerda**, sem conteúdo visível. É indistinguível de "o dialog quebrou", e só acontece no celular.

Regra, em todo componente de `components/ui/` que renderize campo nativo (`input.tsx`, `textarea.tsx`,
`command.tsx` — o `CommandInput` do `EntityPicker` —, qualquer `*Input` próprio):

```tsx
// mobile-first: a classe SEM prefixo é a do celular; `md:` devolve a densidade do desktop
"… text-base … md:text-sm"        // ou md:text-xs/relaxed, conforme a escala do projeto
```

Campo que **herda** a fonte de um wrapper (`ComboboxChipsInput` dentro de um `ComboboxChips`
`text-xs`) precisa da classe **no próprio input** — a herança traz o valor abaixo do limiar.

**NUNCA** resolva isso com `maximum-scale=1`/`user-scalable=no` (mata o pinch-zoom, WCAG 1.4.4) nem
com regra global `input { font-size: 16px !important }` (atropela campo intencionalmente maior).

### `viewport-fit=cover` é app-wide — compense no mesmo commit

Passa a pintar conteúdo sob notch / Dynamic Island / home indicator em **toda** tela:

1. `padding-left/right: env(safe-area-inset-left/right)` no container de topo do `SidebarLayout` — em
   landscape o notch come ~44px da borda.
2. `offset` no `<Toaster>` do sonner (toast ficaria sob o home indicator).
3. Toda superfície `fixed inset-0` fora do `FormDialog` (lightbox, viewer fullscreen).
4. Conferir o background do `<body>` em dark mode — a faixa atrás dos insets pinta o fundo do `<html>`.
5. Shell com `h-[100dvh] overflow-hidden` passa a refluir no Android quando o teclado sobe. Trocar por
   `flex-1 min-h-0` (que já é a regra do gate — ver `layouts.tsx`).

## `FormDialog` — o que ele garante

- **Mobile (<768px):** ancorado na visual viewport, full-bleed, 3 faixas (header fixo / corpo rolável /
  footer fixo). Só a borda de baixo se move quando o teclado sobe — o título fica parado.
- **Desktop:** centralizado, `min(85vh, vv-height − 2rem)`, `size` de 4 degraus.
- Scroll pro campo focado por aritmética sobre `scrollTop`. **NUNCA `scrollIntoView`** — no iOS ele
  sobe pela cadeia de ancestrais e rola o documento, deslocando a visual viewport de novo.
- `blur()` antes de fechar e antes de submeter (o iOS deixa o teclado órfão quando o campo focado sai
  do DOM).
- `env(safe-area-inset-bottom)` no footer, `env(safe-area-inset-top)` no header.

### `transform: none` NÃO desliga o `-translate-x-1/2` no Tailwind 4

O `compactStyle` precisa das **duas** linhas:

```ts
transform: "none",
translate: "none",
```

O `DialogContent` centra com `fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2`. No
Tailwind **3** isso virava `transform: translate(-50%, -50%)` e um `transform: none` inline matava.
No Tailwind **4** vira a propriedade autônoma:

```css
.-translate-x-1\/2 { --tw-translate-x: -50%; translate: var(--tw-translate-x) var(--tw-translate-y); }
```

`translate` e `transform` são propriedades **independentes** (as duas compõem a matriz final), então
`transform: none` não encosta nela. O full-bleed sobrevive com `left: 0; width: 100%;
height: var(--vv-height)` **e** `translate: -50% -50%` — anda metade da própria largura pra esquerda e
metade da altura pra cima. Sintoma exato: **o dialog aparece com a metade direita ocupando só a
metade esquerda da tela, cortado no topo, e não dá pra ver o conteúdo**. Só no celular, porque só o
ramo compacto zera a geometria.

Diagnóstico rápido no DevTools: se a borda direita do dialog cai em ~50% da largura do aparelho e a
altura visível é ~50% da tela, é isto — não é `vh`, não é teclado, não é zoom.

O mesmo vale pra `scale` e `rotate` (Tailwind 4 emite as três autônomas). Se um dia o full-bleed
precisar zerar escala, é `scale: "none"`, não `transform`.

### Autofocus: são DUAS supressões

`preventDefault()` no `onOpenAutoFocus` (o do Radix) **e** remover `autoFocus` do primeiro `<Input>`
(o React chama `.focus()` por conta própria, independente do Radix). Esquecer a segunda é o erro mais
comum da migração — `rg -n "autoFocus" src/components` depois de migrar.

### Falsos positivos filtrados

- `KEYBOARD_MIN_INSET_PX = 120` — o colapso da barra de endereço do iOS muda `innerHeight` em ~50–90px
  e seria lido como "teclado pequeno".
- Guarda de `scale` — pinch-zoom encolhe `vv.height` e colapsaria o dialog.

## Tabela de `size`

| `size` | Classe | Quando |
| --- | --- | --- |
| `sm` | `sm:max-w-md` | confirm, escolha simples, filtros |
| `md` | `sm:max-w-lg` | form curto |
| `lg` | `sm:max-w-lg lg:max-w-2xl` | **default** — form médio |
| `xl` | `sm:max-w-lg lg:max-w-3xl xl:max-w-4xl` | snippet/tabela, quick-create |

**Cada degrau recrava `sm:` de propósito.** A base do `DialogContent` traz um `sm:max-w-*` próprio, e
`cn`/tailwind-merge **não** deduplica variantes diferentes — um `lg:max-w-2xl` solto perde toda a faixa
de 640 a 1024px pro `sm:` da base. Foi bug real em `overlays.md` antes desta reference existir.

## vaul (Drawer) não entra aqui

É Radix Dialog por baixo: mesmo `react-remove-scroll`, mesmo deslocamento no iOS. E drag-to-dismiss
num form de 30 campos divide o gesto físico com o scroll do corpo — perder o formulário preenchido num
swipe acidental é falha catastrófica. O problema é medição + CSS, não modelo de interação. Drawer
segue reservado a wizard gestual mobile de 3+ passos (`overlays.md`).

## Verificação

**jsdom** (Vitest) cobre a lógica inteira, stubando `visualViewport` como `EventTarget`: escrita e
limpeza das CSS vars, refcount com dialog aninhado, threshold de 120px, guarda de pinch-zoom,
aritmética do scroll pro campo focado, `scrollIntoView` NÃO chamado, supressão de autofocus, footer
fora do container de scroll. Não cobre nada de layout — jsdom não tem layout engine.

**Playwright** com `visualViewport` fakeado via `addInitScript` dá renderer real + `boundingBox()`:
é o teste de geometria de maior valor que não exige device. Playwright **não** levanta teclado real em
navegador nenhum (o WebKit dele não é o Safari do iOS).

**Device** (Simulador iOS + Web Inspector cobre quase tudo de graça; iPhone real só pro modo
standalone):

1. teclado sobe → footer visível
2. focar o **último** campo → ele sobe acima do teclado
3. o dialog não sai pela borda de cima
4. landscape com teclado aberto (é onde o corpo fica mais apertado)
5. quick-create a partir de `EntityPicker` dentro de dialog, rolando a lista do picker
6. fechar com teclado aberto → o teclado some
7. standalone: título livre da Dynamic Island, footer livre do home indicator
