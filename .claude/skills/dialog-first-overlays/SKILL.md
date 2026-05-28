---
name: dialog-first-overlays
description: Padrão Dialog-first para QUALQUER overlay em React + shadcn — Dialog é default (forms secundários, snippets/code, detail views, confirms, pickers, share, edit). Sheet/Drawer só com motivo escrito (inspector lateral persistente / mobile wizard com swipe). Inclui width recommendations por tipo de conteúdo (`sm:max-w-md` confirm, `lg:max-w-2xl` default, `lg:max-w-3xl xl:max-w-4xl` snippet/table-heavy), `max-h-[85vh] overflow-y-auto` para conteúdo alto, anti-padrão full-screen. INVOCAR ANTES de — criar qualquer modal/popup/overlay, decidir Dialog vs Sheet vs Drawer vs Popover vs Tooltip, abrir form sobre conteúdo, criar confirm dialog, criar detail view popup, criar picker complexo, criar share/edit/copy snippet. NUNCA use Sheet/Drawer sem justificativa escrita no código ("precisa ficar lado-a-lado" ou "mobile wizard com swipe"); NUNCA full-screen exceto wizard real; NUNCA esqueça `max-h-[85vh] overflow-y-auto` em conteúdo alto.
---

# Dialog-First Overlays (React + shadcn/ui)

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
- ❌ Confirm "tem certeza?". → Dialog (`AlertDialog`).

Se a justificativa não cabe num comentário de 1 linha acima do componente, é Dialog.

## Quando NÃO usar Drawer (vaul)

Drawer é gesture-driven mobile. Em desktop, parece Sheet pior. Em mobile flow simples, parece Dialog pior.

- ✅ Wizard mobile de 3+ passos com swipe-to-next, swipe-down-to-dismiss.
- ❌ Form responsivo "preciso de algo que funcione mobile e desktop". → Dialog (já é responsivo).
- ❌ Bottom sheet pra escolher 1 opção. → Dialog com `sm:max-w-md`.

## Width recommendations

```tsx
<DialogContent className="sm:max-w-md">             {/* confirm, pick simples */}
<DialogContent>                                      {/* default: ~sm:max-w-lg */}
<DialogContent className="lg:max-w-2xl">            {/* form médio (default recomendado) */}
<DialogContent className="lg:max-w-3xl xl:max-w-4xl"> {/* snippet/code/table-heavy */}
```

**NUNCA** full-screen (`w-screen h-screen`) — exceto wizard real (e aí use Drawer).

## Conteúdo alto → scroll vertical

```tsx
<DialogContent className="lg:max-w-2xl max-h-[85vh] overflow-y-auto">
  {/* conteúdo longo aqui */}
</DialogContent>
```

`85vh` deixa respiro pro overlay não tocar topo/base. `overflow-y-auto` scroll só quando precisa. **NUNCA** `overflow-y-scroll` (sempre mostra scrollbar mesmo sem conteúdo).

## Pattern básico — controlled Dialog

```tsx
import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export function EditUserDialog({ user }: { user: User }) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">Editar usuário</Button>
      </DialogTrigger>
      <DialogContent className="lg:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Editar usuário</DialogTitle>
          <DialogDescription>
            Altere os dados de {user.name} e salve.
          </DialogDescription>
        </DialogHeader>
        <UserEditForm user={user} onSuccess={() => setOpen(false)} />
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancelar
          </Button>
          <Button type="submit" form="user-edit-form">
            Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

## Confirm Dialog (AlertDialog)

Para confirmações destrutivas (delete, archive, etc.) use `AlertDialog` — sem dismiss por click-fora, força o user a escolher.

```tsx
<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="destructive">Excluir conta</Button>
  </AlertDialogTrigger>
  <AlertDialogContent className="sm:max-w-md">
    <AlertDialogHeader>
      <AlertDialogTitle>Excluir conta permanentemente?</AlertDialogTitle>
      <AlertDialogDescription>
        Esta ação não pode ser desfeita. Todos os dados serão removidos.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancelar</AlertDialogCancel>
      <AlertDialogAction onClick={handleDelete}>Excluir</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

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
- **NUNCA** use Drawer pra flow desktop ou mobile-flow-simples.
- **NUNCA** full-screen dialog exceto wizard real.
- **NUNCA** esqueça `max-h-[85vh] overflow-y-auto` em conteúdo potencialmente alto — vira dialog que sangra pra fora da tela.
- **NUNCA** `overflow-y-scroll` (sempre mostra scrollbar).
- **NUNCA** confunda Popover (inline, ancora num elemento) com Dialog (centro da tela, modal).
- **NUNCA** abra Dialog dentro de Dialog — flatten o flow ou use stepper inline.
