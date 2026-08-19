# Dialog-First Overlays (React + shadcn/ui)

> Reference do gate `frontend` (item 2 do checklist). Tabela de Dialog vs Sheet vs Drawer + tamanhos.

**Dialog é o default** para qualquer superfície que aparece por cima do conteúdo. UX superior em ~95% dos casos: centralizado, foco visual claro, dismiss por click-fora/ESC retorna o usuário ao estado exato anterior. Use Sheet/Drawer APENAS quando puder escrever a justificativa.

## Tabela de decisão

| Cenário                                                          | Use                                                       |
| ---------------------------------------------------------------- | --------------------------------------------------------- |
| Form curto/médio, snippet, confirm, detail, picker, share, edit  | **Dialog**                                                |
| Tooltip rápido, info inline, hint                                | Popover / HoverCard                                       |
| Menu de ações contextual (right-click, ⋯)                        | DropdownMenu / ContextMenu                                |
| Inspector lateral PERSISTENTE durante navegação (raro)           | Sheet (com justificativa explícita: por que persiste)     |
| Wizard mobile multi-step com gestures de swipe                   | Drawer (vaul) — mobile-only flow                          |

Regra de "abre, faz uma coisa, fecha" → **Dialog**, sem discussão.

## Quando NÃO usar Sheet

Sheet é grande, ocupa lateral, e o conteúdo principal continua visível atrás. Isso só faz sentido se o usuário precisa **ver os dois ao mesmo tempo** durante uma sequência de ações.

- ✅ Inspector de seleção: lista de items na esquerda, detalhes do selecionado na direita persistente. User pode trocar de item sem fechar/abrir.
- ❌ Form de edição que abre, salva, fecha. → Dialog.
- ❌ Detail view que abre, vê, fecha. → Dialog.
- ❌ Confirm "tem certeza?". → `ConfirmDialog` (AlertDialog central).

Se a justificativa não cabe num comentário de 1 linha acima do componente, é Dialog.

## Quando NÃO usar Drawer (vaul)

Drawer é gesture-driven mobile. Em desktop, parece Sheet pior. Em mobile flow simples, parece Dialog pior.

- ✅ Wizard mobile de 3+ passos com swipe-to-next, swipe-down-to-dismiss.
- ❌ Form responsivo "preciso de algo que funcione mobile e desktop". → Dialog (já é responsivo).
- ❌ Bottom sheet pra escolher 1 opção. → Dialog com `sm:max-w-md`.

## Dialog com formulário → `FormDialog` (SEMPRE)

Qualquer dialog que contenha campo de input usa **`ui/form-dialog.tsx`**, nunca `DialogContent` cru.
Ele entrega 3 faixas (header fixo / corpo rolável / footer fixo) e — o motivo de existir — ancora o
dialog na **visual viewport** no mobile, para o teclado do celular não esconder os campos e o
Salvar/Cancelar. Fonte: `references/form-dialog.tsx`. Fundamentação e verificação:
`references/mobile-keyboard.md`.

```tsx
<FormDialog
  open={open} onOpenChange={onOpenChange} busy={mutation.isPending}
  size="lg"
  title="Editar usuário" description="Altere os dados e salve."
  bodyClassName="space-y-4"
  onSubmit={() => form.handleSubmit()}
  footer={<Button type="submit" disabled={mutation.isPending}>Salvar</Button>}
>
  {/* campos */}
</FormDialog>
```

| `size` | Classe | Quando |
| ------ | ------ | ------ |
| `sm`   | `sm:max-w-md`                        | confirm, escolha simples, filtros mobile |
| `md`   | `sm:max-w-lg`                        | form curto                               |
| `lg`   | `sm:max-w-lg lg:max-w-2xl`           | **default** — form médio                 |
| `xl`   | `sm:max-w-lg lg:max-w-3xl xl:max-w-4xl` | snippet/code/table-heavy, quick-create |

**Cada degrau recrava o `sm:` de propósito.** A base do `DialogContent` traz um `sm:max-w-*` próprio e
`cn`/tailwind-merge **não** deduplica variantes diferentes — um `lg:max-w-2xl` solto perde toda a faixa
de 640 a 1024px pro `sm:` da base. Foi bug real desta reference antes do `FormDialog` existir.

## Como se sai do overlay (quem tem "Cancelar" e quem tem "X")

São dois contratos, e eles não se misturam. A pergunta é **o overlay força uma escolha?**

| Overlay                                                     | X no topo | Click-fora / ESC | Botão de dispensa no footer            |
| ----------------------------------------------------------- | --------- | ---------------- | -------------------------------------- |
| `ConfirmDialog` / `AlertDialog` — confirmar, excluir, sair  | **não**   | **não**          | **sim** — `Cancelar` + a ação, só isso |
| Qualquer outro Dialog / `FormDialog` — form, detalhe, picker | **sim**   | **sim**          | **NÃO**                                |

O footer de um `FormDialog` carrega **só a ação afirmativa**. `Cancelar`/`Fechar`/`Voltar` ao lado
do X é a MESMA saída oferecida duas vezes: rouba largura do footer (que no celular é
`flex-col-reverse`, então o botão inútil vira a linha de baixo, encostada no safe-area), compete
com o alvo de toque do Salvar e ainda sugere que "fechar" e "cancelar" fazem coisas diferentes —
não fazem, os dois só chamam `onOpenChange(false)`. O X e o click-fora já são a saída, são
descobertos sem leitura e existem por padrão (`showCloseButton`/`dismissible` nascem `true`).

O `AlertDialog` é o oposto de propósito: ele **não** tem `Close`, o Radix não dispensa por
click-fora, e é por isso que a dupla `Cancelar` + ação afirmativa é obrigatória lá — sem ela o
usuário fica preso. Não "padronize" um removendo o Cancelar do outro.

Fica no footer o que é **ação de negócio**, mesmo com nome parecido: "Fechar caixa" (submit),
"Cancelar orçamento" (a ação destrutiva de um confirm), "Cancelar" como transição de status,
"Voltar" que retrocede um passo de wizard (`setStep(1)`, não dispensa). O teste é único: se o
`onClick` só fecha o overlay, o botão não deveria existir.

Dialog não-dispensável (onboarding obrigatório) fecha os dois canais junto —
`dismissible={false}` some com o X **e** com o click-fora; aí, se houver saída, ela é um botão
explícito com verbo próprio ("Sair sem salvar"), não um "Cancelar" genérico.

## Width — Dialog sem formulário

```tsx
<DialogContent className="sm:max-w-md">                 {/* confirm, pick simples */}
<DialogContent className="sm:max-w-lg lg:max-w-2xl">    {/* detalhe médio */}
<DialogContent className="sm:max-w-lg lg:max-w-3xl xl:max-w-4xl"> {/* snippet/code/table */}
```

**NUNCA** full-screen no **desktop** (`w-screen h-screen`) — exceto wizard real (e aí use Drawer).
Abaixo de 768px, full-bleed é o **padrão** para dialog com formulário, e quem entrega isso é o
`FormDialog`: num form de 30 campos a margem lateral vira faixa de dismiss acidental, e é a única
geometria que mantém o footer acima do teclado. Não reimplemente na mão.

## Geometria à prova de viewport (mora na BASE do `DialogContent`)

O `DialogContent` canônico **já nasce contido**, no próprio `ui/dialog.tsx` — call site não precisa
lembrar de nada:

```tsx
"max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] overflow-y-auto overscroll-contain",
// abaixo de 768px o call site NÃO manda na geometria
"max-md:max-h-[calc(100svh-3rem)] max-md:max-w-[calc(100%-2rem)]",
```

Por que na base e não no call site:

- `-translate-y-1/2` centra pela **altura do conteúdo**. Passando da tela, a metade de cima vai pra
  fora e **nenhum scroll alcança** — é `position: fixed` e o body está travado pelo
  `react-remove-scroll`. Foi o bug real "o dialog sai pra cima e não dá pra ver o conteúdo".
- No eixo X o mesmo `overflow-y-auto` já **força `overflow-x: auto`** (regra do CSS: um eixo
  não-`visible` promove o outro). Conteúdo largo — imagem sem `max-w-full`, tabela, `<pre>` — rola
  dentro do dialog em vez de esticar o documento e fazer a página inteira panar pro lado ("sai pra
  esquerda").
- `w-[calc(100%-2rem)]` e **não** `w-full`: call site que troca o `max-w` (`max-w-4xl`) não pode
  levar junto a margem lateral do mobile.

Confiar nisso é o padrão — `max-h-[85vh] overflow-y-auto` no call site virou redundante (não é erro,
só ruído). Quem **quer** outra geometria continua mandando, via tailwind-merge: `overflow-hidden`
num split com scroller próprio, `h-[92vh]` num viewer.

### A segunda linha (`max-md:`) é a trava do celular

O tailwind-merge só deduplica classes do **mesmo** grupo E **mesma** variante: `max-h-[85vh]` do call
site substitui o `max-h-[calc(100dvh-2rem)]` da base, mas **não toca** no `max-md:max-h-*` — é outra
chave. E o Tailwind emite variante depois da utility crua, então abaixo de 768px o `max-md:` vence
no cascade. Resultado: nenhum call site consegue vazar medida de desktop pro telefone.

Por que isso importa: `max-h-[85vh]`, `h-[92vh]`, `max-w-4xl` são números escolhidos olhando um
monitor. No iOS `vh` é a viewport **grande** (a que ignora as barras do browser), então `85vh` é
~100% da área realmente visível — o dialog, centrado pela **layout** viewport, nasce com a metade
de cima embaixo da barra de endereço. `svh` é a viewport **pequena** (cabe com as barras abertas),
então `calc(100svh-3rem)` fica certo independente do estado das barras. E `max-w-4xl` = 56rem, que
com root de 17px dá 952px — bem mais largo que qualquer telefone.

Full-bleed proposital no celular (lightbox, viewer de imagem) é opt-in explícito no call site:
`max-md:max-h-none max-md:max-w-none`.

**NUNCA** `overflow-y-scroll` (mostra scrollbar mesmo sem conteúdo).

Dialog **com** formulário: nada disso importa — é `FormDialog`, que já resolve altura e scroll.
Deixar um `overflow-y-auto` residual no `className` dele cria um segundo scroller e o footer rola
pra fora da tela.

## Pattern básico — controlled Dialog (SEM formulário)

Detalhe, leitura, snippet. Com formulário é `FormDialog` (seção acima).

```tsx
import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export function UserDetailDialog({ user }: { user: User }) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">Ver detalhes</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg lg:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{user.name}</DialogTitle>
          <DialogDescription>Cadastro, permissões e histórico.</DialogDescription>
        </DialogHeader>
        <UserSummary user={user} />
      </DialogContent>
    </Dialog>
  );
}
```

## Dialog deep-linkado via search param

Para overlay cujo estado merece sobreviver a F5 e ser compartilhável por link — hub de settings, inspector de item, guia. Dialogs efêmeros de ação (confirm, form de criação) continuam com `useState` local.

```tsx
// 1. A rota-casca (a que envolve o Outlet) valida o param — valor inválido vira undefined (fechado)
const SECTION_IDS = ["members", "queues", "agent"] as const;
type SectionId = (typeof SECTION_IDS)[number];

validateSearch: (s: Record<string, unknown>): { settings?: SectionId } => ({
  settings: SECTION_IDS.includes(s.settings as SectionId) ? (s.settings as SectionId) : undefined,
}),

// 2. O Dialog é controlado pela PRESENÇA do param — sem boolean "open" separado
const { settings } = useSearch({ strict: false });
const navigate = useNavigate();
const open = (id: SectionId) => navigate({ to: ".", search: (p) => ({ ...p, settings: id }) });
const close = () => navigate({ to: ".", search: (p) => ({ ...p, settings: undefined }) });

<Dialog open={!!settings} onOpenChange={(o) => !o && close()}>
```

- Abrir/fechar = push (voltar do browser fecha o dialog); **trocar de seção** = `replace: true` (não polui o histórico).
- SEMPRE spread `...prev` no `search` — apagar params alheios (filtros, period) é regressão silenciosa.
- Lazy mount: só a seção ativa renderiza (`{settings === "members" && <MembersSection />}`).
- O componente do dialog monta na CASCA (junto do Outlet), não em página — disponível em qualquer rota.
- Hub de settings completo (nav lateral + busca + permission gating + mobile + variante org-scoped) → ver `settings-dialog.md`.

## Confirm Dialog — `ConfirmDialog` (padrão ÚNICO)

Confirmação destrutiva (delete, archive, remove) SEMPRE pelo componente canônico
**`ui/confirm-dialog.tsx`** (wrapper sobre `AlertDialog` shadcn — sem dismiss por click-fora, força
uma escolha). Fonte: `references/confirm-dialog.tsx` (vendored por projeto). NUNCA reimplemente o
confirm na mão.

```tsx
// Padrão em lista: um único ConfirmDialog no container, controlado pelo item selecionado.
const [toDelete, setToDelete] = useState<Doc | null>(null);

<DropdownMenuItem variant="destructive" onClick={() => setToDelete(doc)}>
  <Trash2 className="size-3.5" /> Excluir
</DropdownMenuItem>

<ConfirmDialog
  open={!!toDelete}
  onOpenChange={(o) => !o && setToDelete(null)}
  title="Excluir documento?"
  description="Esta ação não pode ser desfeita."
  confirmLabel="Excluir"
  destructive
  busy={del.isPending}
  onConfirm={() => toDelete && del.mutate(toDelete.id, { onSuccess: () => setToDelete(null) })}
/>
```

- `busy` (pending da mutation) desabilita os botões, mostra label pendente e segura o dialog aberto;
  o parent fecha no `onSuccess` via `onOpenChange(false)`/reset do item.
- Confirm não-destrutivo (publicar, enviar) usa o mesmo componente sem `destructive`.

### Anti-padrões (PROIBIDO — é o que esta regra existe pra matar)

- ❌ **Tira de confirmação inline / "accordion"** abaixo do item (`{confirmDelete && <div className="border-t p-3">…Cancelar/Excluir…</div>}`).
- ❌ **Button-swap**: o botão de excluir vira "Confirmar" na própria linha.
- ❌ **`window.confirm(...)`** nativo.
- ❌ **Dialog/AlertDialog ad-hoc** reimplementado por feature em vez do `ConfirmDialog`.
- ❌ Confirmar destrutivo num `Dialog` comum (dismiss por click-fora descarta sem escolha).

## Snippet/Code Dialog

Para mostrar código copiável (snippet de cURL, payload JSON, instrução SQL):

```tsx
<DialogContent className="lg:max-w-3xl xl:max-w-4xl max-h-[85vh] overflow-y-auto">
  <DialogHeader>
    <DialogTitle>Webhook payload</DialogTitle>
  </DialogHeader>
  <pre className="whitespace-pre-wrap break-all rounded bg-muted p-4 text-sm">
    <code>{payload}</code>
  </pre>
  <DialogFooter>
    <Button onClick={() => copyToClipboard(payload)}>Copiar</Button>
  </DialogFooter>
</DialogContent>
```

Note `whitespace-pre-wrap break-all` no `<pre>` — sempre quebra, nunca scroll horizontal (regra firme em `frontend.md`).

## Don'ts

- **NUNCA** use Sheet sem justificativa escrita ("user precisa ver lado-a-lado" ou "persistente durante navegação").
- **NUNCA** use Drawer pra flow desktop ou mobile-flow-simples. (vaul não é dependência de nenhum projeto — e **não** é a resposta pro teclado mobile: é Radix Dialog por baixo, com o mesmo deslocamento de visual viewport no iOS, e drag-to-dismiss divide o gesto com o scroll do corpo. Ver `mobile-keyboard.md`.)
- **NUNCA** full-screen dialog **no desktop** exceto wizard real. Abaixo de 768px, dialog de formulário é full-bleed por padrão — via `FormDialog`, nunca na mão.
- **NUNCA** `DialogContent` cru pra dialog com campo de input — é `FormDialog`. `max-h-[85vh] overflow-y-auto` num form dialog é o padrão ANTIGO: no iOS o teclado não encolhe a layout viewport, então `vh`/`dvh` não ajudam e os campos de baixo somem atrás dele.
- **NUNCA** remova `max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] overflow-y-auto` nem o par `max-md:max-h-[calc(100svh-3rem)] max-md:max-w-[calc(100%-2rem)]` da base do `DialogContent` — é o que segura o dialog dentro da tela nos dois eixos e impede o call site de vazar medida de desktop pro celular (seção "Geometria à prova de viewport"). Um `overflow-hidden` no call site é decisão consciente; apagar da base é regressão.
- **NUNCA** deixe campo nativo (`<input>`/`<textarea>`/`<select>`) com fonte computada < 16px no celular — `text-sm` com root de 17px dá 14.875px, o iOS dá auto-zoom e o dialog `position: fixed` some pra cima/pra esquerda. É `text-base … md:text-sm` (ver `mobile-keyboard.md`).
- **NUNCA** deixe `overflow-y-auto` residual no `className` de um `FormDialog` — cria segundo scroller e o footer rola pra fora.
- **NUNCA** `overflow-y-scroll` (sempre mostra scrollbar).
- **NUNCA** deixe `autoFocus` no primeiro input de um `FormDialog` — o React chama `.focus()` sozinho e sobe o teclado por cima da animação de abertura, anulando a supressão que o componente faz no `onOpenAutoFocus`.
- **NUNCA** botão `Cancelar`/`Fechar`/`Voltar` no footer de Dialog/`FormDialog` — o X e o click-fora já são a saída, e o par duplicado esmaga o footer no celular. O footer leva só a ação afirmativa. O `ConfirmDialog` é a exceção obrigatória (não tem X nem click-fora — sem o `Cancelar` o usuário fica preso). Ver "Como se sai do overlay".
- **NUNCA** remova o `AlertDialogCancel` de um `ConfirmDialog` nem adicione X nele "por consistência" — ele existe para FORÇAR uma escolha.
- **NUNCA** confunda Popover (inline, ancora num elemento) com Dialog (centro da tela, modal).
- Dialog dentro de Dialog: SÓ em dois casos — (a) hub→ação efêmera (ex.: hub de settings deep-linkado com detail/confirm `useState` por cima — Radix empilha foco/z-index, Esc fecha só o topo); (b) quick-create de FK picker (`*FormDialog` quase-fullscreen aberto pelo CTA "Novo…" do `EntityPicker` — ver `entity-picker.md`). Flow linear ainda é flatten/stepper inline.
- **NUNCA** param booleano `open` separado do param de seção num dialog deep-linkado — a presença da seção É o aberto.
