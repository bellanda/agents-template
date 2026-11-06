# Balão de onboarding (popover "visto uma vez" por usuário)

> Reference do gate `frontend`. Abra ANTES de apresentar uma tela/botão novo ao usuário com uma dica
> única. Canônicos copiados aqui (idênticos ao kailos, só referência): `onboarding-balloon.tsx`
> (-> `components/onboarding/OnboardingBalloon.tsx`) e `balloon-slot.ts` (-> `balloon-slot.ts`).
> Depende de `lib/help/help-seen`, `useAppStyleChoicePending` e `ui/popover` do app. CRM 2030, 2026-11-05.

```tsx
<OnboardingBalloon id="crm-lista" title="…" description="…" side="bottom">
  <Button>Alvo</Button>   {/* precisa aceitar ref */}
</OnboardingBalloon>
```

## Invariantes

- **Visto uma vez por USUÁRIO, não por aparelho.** "Entendi" (ou fechar) grava `balloon:<id>` na MESMA
  lista das ajudas (`ui_preferences.help_seen`, unida no servidor, sem migration) via
  `PATCH /accounts/me/ui-preferences`, em background e silencioso (falhar = no pior caso o balão volta).
  Cache local (`markTopicSeenLocally`) evita repetir na mesma sessão. `id` estável, <= 56 caracteres.
- **Um balão por vez** (`balloon-slot.ts`, estado de módulo de propósito: balões vivem em subárvores
  não relacionadas). O primeiro elegível ocupa o slot, os outros entram na fila e abrem em ordem quando
  o atual é dispensado ou desmonta (`requestBalloonSlot`/`releaseBalloonSlot`, idempotentes). Motivo: no
  `/chat` a faixa e o painel abriam dois popovers sobrepostos.
- **O mesmo balão montado 2x (coluna desktop + botão do celular trocados por CSS): só a cópia VISÍVEL
  abre.** Um `<span class="sr-only">` sonda ao lado do alvo e `checkVisibility()` decide; sem a API
  (jsdom, Safari antigo) conta como visível (pior caso: abrem os dois).
- **Não rouba foco** (`onOpenAutoFocus` com `preventDefault`) nem trava a tela.
- `enabled={false}` segura o balão até o alvo existir (dado carregando). Não abre durante a escolha
  de estilo do app (`useAppStyleChoicePending`).
- Sem filho: ancora no canto superior esquerdo do ancestral posicionado.
- **Nunca abre por cima de um dialog modal.** O Radix marca tudo fora do modal com
  `data-aria-hidden` (`hideOthers`); se a sonda está dentro de um ancestral marcado, o balão espera
  (`useIsBehindModal`, um `MutationObserver` no `body` filtrado em `data-aria-hidden`, só enquanto o
  balão poderia abrir). Esperar NÃO conta como visto: o balão volta quando o dialog fecha. Motivo
  (kailos 2026-11-05): o deep link `?attendance=` abria o balão da lista sobre o dialog e ele engolia
  os toques.
- **Tocar no controle apontado também é "Entendi"** (`onClickCapture` no `PopoverAnchor` enquanto
  aberto). No toque o Radix só dispensa no clique SEGUINTE, depois que o controle já abriu o próprio
  dialog embaixo do balão (tablet: o balão do botão "Cliente" ficava aberto junto do painel).

## QA visual / Playwright

O balão **intercepta cliques** (cobre header e menu do usuário): no setup da rota, dispense-o antes de
interagir. Kailos `frontend/e2e/visual/routes.ts` `dismissListBalloon`: localiza
`[data-slot=popover-content]` com o texto do título, `waitFor visible` (timeout 3 s; `catch` = já visto),
clica "Entendi" e espera `toBeHidden`. Dispense só o balão que atrapalha: o balão de um dialog faz parte
do print desse dialog. Em E2E de outras telas, pré-semeie `help_seen` com a marca.
Com balão aberto, `getByRole('dialog')` pode casar 2 elementos (o popover também é `dialog`): no
strict mode o locator quebra, e no desktop o `.first()` pegava o balão como "superfície". Localize o
dialog pelo slot (`[data-slot=form-dialog]`/`[data-slot=dialog-content]`), nunca pelo role puro.

## Testes

`components/onboarding/__tests__/OnboardingBalloon.test.tsx` (aparece na 1a vez e "Entendi" grava no
servidor; não reaparece com marca no cache local ou em `/accounts/me`; dois balões = um por vez) e
`balloon-slot.test.ts` (fila na ordem, dedupe, liberar lugar na fila). Também: espera atrás de um
modal e volta sem marcar visto; tocar no alvo conta como entendido.
