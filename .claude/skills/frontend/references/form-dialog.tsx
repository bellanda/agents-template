import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import * as React from "react";

/* ════════════════════════════════════════════════════════════════════════════
   useVisualViewport

   A *layout viewport* (base do `position: fixed`, do `100vh`/`100dvh` e do
   `window.innerHeight`) NÃO reage ao teclado no iOS — `dvh` acompanha o colapso
   da barra de endereço, não o teclado. Quem encolhe é a *visual viewport*.
   E como o body está travado pelo `react-remove-scroll`, o WebKit não consegue
   rolar o documento pra revelar o campo focado: ele desloca a área visível
   dentro da layout viewport (`visualViewport.offsetTop > 0`). O DialogContent,
   sendo `position: fixed`, fica colado na layout viewport e sai pela borda de
   cima. Nenhum ajuste de vh/dvh/svh corrige isso — só compensar o `offsetTop`.
   ════════════════════════════════════════════════════════════════════════════ */

export interface VisualViewportMetrics {
  /** Altura realmente visível, em px. */
  height: number;
  /** Quanto a área visível desceu dentro da layout viewport (iOS empurra ao focar). */
  offsetTop: number;
  /** Altura da layout viewport oculta pelo teclado. 0 sob `interactive-widget=resizes-content`. */
  keyboardInset: number;
}

/** Abaixo disto é chrome do browser (barra de endereço colapsando), não teclado. */
const KEYBOARD_MIN_INSET_PX = 120;
/** Fora da escala 1 é pinch-zoom: `vv.height` encolhe e não significa teclado. */
const SCALE_EPSILON = 0.01;

const CSS_VAR_HEIGHT = "--vv-height";
const CSS_VAR_OFFSET_TOP = "--vv-offset-top";
const CSS_VAR_KEYBOARD_INSET = "--vv-keyboard-inset";

type Subscriber = (metrics: VisualViewportMetrics) => void;

// Singleton com refcount. As custom properties moram em <html>, então dois
// dialogs aninhados (quick-create do EntityPicker) não podem duplicar listeners
// nem apagar as vars do pai quando o filho desmonta.
const subscribers = new Set<Subscriber>();
let pendingFrame = 0;

function measure(): VisualViewportMetrics {
  const layoutHeight = window.innerHeight;
  const viewport = window.visualViewport;
  if (!viewport) return { height: layoutHeight, offsetTop: 0, keyboardInset: 0 };

  const zoomed = Math.abs(viewport.scale - 1) > SCALE_EPSILON;
  const inset = zoomed ? 0 : Math.max(0, layoutHeight - viewport.height);
  return {
    height: viewport.height,
    offsetTop: viewport.offsetTop,
    keyboardInset: inset < KEYBOARD_MIN_INSET_PX ? 0 : inset,
  };
}

function publish() {
  pendingFrame = 0;
  const metrics = measure();
  const root = document.documentElement.style;
  root.setProperty(CSS_VAR_HEIGHT, `${metrics.height}px`);
  root.setProperty(CSS_VAR_OFFSET_TOP, `${metrics.offsetTop}px`);
  root.setProperty(CSS_VAR_KEYBOARD_INSET, `${metrics.keyboardInset}px`);
  for (const subscriber of subscribers) subscriber(metrics);
}

// O iOS dispara `resize` dezenas de vezes durante a animação do teclado. rAF
// coalesce numa escrita por frame. Debounce por timer NÃO serve: a geometria
// precisa acompanhar a animação, não chegar depois dela.
function schedulePublish() {
  if (pendingFrame) return;
  pendingFrame = window.requestAnimationFrame(publish);
}

function subscribe(subscriber: Subscriber): () => void {
  const isFirst = subscribers.size === 0;
  subscribers.add(subscriber);

  if (isFirst) {
    // `scroll` é o ÚNICO evento emitido quando o iOS desloca a área visível sem
    // mudar o tamanho dela — exatamente focar um campo com o body travado.
    window.visualViewport?.addEventListener("resize", schedulePublish);
    window.visualViewport?.addEventListener("scroll", schedulePublish);
    // Cobre rotação e browsers sem visualViewport.
    window.addEventListener("resize", schedulePublish);
  }
  publish();

  return () => {
    subscribers.delete(subscriber);
    if (subscribers.size > 0) return;

    if (pendingFrame) {
      window.cancelAnimationFrame(pendingFrame);
      pendingFrame = 0;
    }
    window.visualViewport?.removeEventListener("resize", schedulePublish);
    window.visualViewport?.removeEventListener("scroll", schedulePublish);
    window.removeEventListener("resize", schedulePublish);

    const root = document.documentElement.style;
    root.removeProperty(CSS_VAR_HEIGHT);
    root.removeProperty(CSS_VAR_OFFSET_TOP);
    root.removeProperty(CSS_VAR_KEYBOARD_INSET);
  };
}

/** Leitura síncrona, sem re-render — pra medir dentro de handlers. */
export function readVisualViewport(): VisualViewportMetrics {
  if (typeof window === "undefined") return { height: 0, offsetTop: 0, keyboardInset: 0 };
  return measure();
}

/**
 * Escreve a geometria da área visível em custom properties de `<html>` e devolve
 * só o sinal grosso (`isKeyboardOpen`) pro React.
 *
 * A geometria vai pra CSS, não pra state, porque muda ~15x por animação de
 * teclado — reconciliar isso é desperdício. O booleano vira state porque muda no
 * máximo 2x por abertura e alimenta decisões de render.
 */
export function useVisualViewport(enabled = true): { isKeyboardOpen: boolean } {
  const [isKeyboardOpen, setIsKeyboardOpen] = React.useState(false);

  React.useEffect(() => {
    if (!enabled || typeof window === "undefined") {
      setIsKeyboardOpen(false);
      return;
    }
    return subscribe((metrics) => {
      const next = metrics.keyboardInset > 0;
      setIsKeyboardOpen((current) => (current === next ? current : next));
    });
  }, [enabled]);

  return { isKeyboardOpen };
}

/* ════════════════════════════════════════════════════════════════════════════
   FormDialog
   ════════════════════════════════════════════════════════════════════════════ */

/** Espelha `use-mobile.ts`. Abaixo disto o dialog é full-bleed. */
const COMPACT_BREAKPOINT_PX = 768;
/** Espera a animação do teclado assentar antes de recolocar o campo focado. */
const FOCUS_SCROLL_SETTLE_MS = 120;
/** Respiro acima/abaixo do campo focado ao trazê-lo pra área visível. */
const FOCUS_SCROLL_MARGIN_PX = 24;
/** Recuo do dialog aninhado (quick-create) pro pai aparecer atrás. */
const NESTED_INSET_PX = 24;

export type FormDialogSize = "sm" | "md" | "lg" | "xl";

/**
 * Cada degrau crava `sm:` também: a base do `DialogContent` traz um `sm:max-w-*`
 * próprio (varia por projeto — `sm`, `md` ou `lg`) que, sem isto, venceria toda a
 * faixa de 640 a 1024px. `cn`/tailwind-merge não deduplica variantes distintas.
 */
const SIZE_CLASS: Record<FormDialogSize, string> = {
  sm: "sm:max-w-md",
  md: "sm:max-w-lg",
  lg: "sm:max-w-lg lg:max-w-2xl",
  xl: "sm:max-w-lg lg:max-w-3xl xl:max-w-4xl",
};

const FormDialogDepthContext = React.createContext(0);

function compactMediaQuery() {
  return window.matchMedia(`(max-width: ${COMPACT_BREAKPOINT_PX - 1}px)`);
}

function subscribeCompact(onChange: () => void) {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  const query = compactMediaQuery();
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function getCompactSnapshot() {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return compactMediaQuery().matches;
}

/**
 * Mesmo contrato do `useIsMobile`, mas com leitura SÍNCRONA. O `useIsMobile`
 * resolve em `useEffect` e devolve `false` no primeiro render — aqui isso seria
 * nascer com geometria de desktop e corrigir um frame depois, no meio da
 * animação de abertura.
 */
function useIsCompactViewport() {
  return React.useSyncExternalStore(subscribeCompact, getCompactSnapshot, () => false);
}

/**
 * Recoloca o campo focado dentro da área rolável.
 *
 * NUNCA `scrollIntoView`: no iOS ele sobe pela cadeia de ancestrais e rola o
 * documento, o que desloca a visual viewport de novo e realimenta o problema.
 */
function scrollFocusedFieldIntoView(body: HTMLElement) {
  const focused = document.activeElement;
  if (!(focused instanceof HTMLElement) || !body.contains(focused)) return;

  const bodyBox = body.getBoundingClientRect();
  const fieldBox = focused.getBoundingClientRect();
  const overflowTop = bodyBox.top + FOCUS_SCROLL_MARGIN_PX - fieldBox.top;
  const overflowBottom = fieldBox.bottom + FOCUS_SCROLL_MARGIN_PX - bodyBox.bottom;

  if (overflowTop > 0) body.scrollTop -= overflowTop;
  else if (overflowBottom > 0) body.scrollTop += overflowBottom;
}

/** O iOS mantém o teclado aberto quando o campo focado some do DOM. */
function blurActiveElement() {
  const active = document.activeElement;
  if (active instanceof HTMLElement) active.blur();
}

export interface FormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Presente → o wrapper renderiza o `<form>` e o submit do footer funciona nativo. */
  onSubmit?: (event: React.FormEvent<HTMLFormElement>) => void;
  /** Linha de ações. Fica FORA do container de scroll — sempre acima do teclado. */
  footer?: React.ReactNode;
  size?: FormDialogSize;
  /** Salvando: bloqueia ESC, click-fora e o botão de fechar. */
  busy?: boolean;
  /**
   * `false` → o dialog não pode ser dispensado (onboarding obrigatório, ex.: criar a
   * primeira organização). Diferente de `busy`: some com o "X" em vez de deixá-lo
   * clicável-porém-inerte. O caller fecha por conta própria depois do sucesso.
   */
  dismissible?: boolean;
  /**
   * `false` → click fora não fecha (ESC e "X" continuam valendo). Para wizard/form longo
   * onde o clique acidental destrói trabalho já digitado — não é o mesmo que `dismissible`,
   * que remove TODAS as saídas.
   */
  closeOnOutsideClick?: boolean;
  /** Classe do container de scroll (ex.: `"space-y-4"`). */
  bodyClassName?: string;
  /** Escape hatch no `DialogContent`. */
  className?: string;
  children: React.ReactNode;
}

/**
 * Dialog de formulário com 3 faixas: header fixo / corpo rolável / footer fixo.
 *
 * Mobile (<768px): ancorado na *visual viewport* — `top: offsetTop`,
 * `height: vv-height`. É a única formulação simultaneamente correta no iOS
 * (offsetTop > 0), no Android `resizes-visual` (offsetTop 0, altura encolhida) e
 * no Android `resizes-content` (layout viewport já exclui o teclado) — sem
 * branch de plataforma e sem risco de compensar duas vezes.
 * Desktop: centralizado, com o `max-h-[85vh]` histórico.
 */
export function FormDialog({
  open,
  onOpenChange,
  title,
  description,
  onSubmit,
  footer,
  size = "lg",
  busy = false,
  dismissible = true,
  closeOnOutsideClick = true,
  bodyClassName,
  className,
  children,
}: FormDialogProps) {
  const depth = React.useContext(FormDialogDepthContext);
  const isCompact = useIsCompactViewport();
  const { isKeyboardOpen } = useVisualViewport(open);
  const contentRef = React.useRef<HTMLDivElement>(null);
  // Callback ref e NÃO `useRef`: o Portal do Radix devolve `null` no primeiro
  // render e só monta os filhos num `useLayoutEffect` — com `ref` o corpo ainda
  // é `null` quando este efeito roda, e como ele não re-roda depois, o listener
  // de `focusin` nunca chegaria a existir. O nó vira dep do efeito.
  const [body, setBody] = React.useState<HTMLDivElement | null>(null);

  // Dois gatilhos, um caminho: foco novo (teclado já aberto, sem resize a
  // caminho) e assentamento da visual viewport (teclado subindo). Trailing-edge.
  React.useEffect(() => {
    if (!open || !isCompact || !body) return;

    let timer = 0;
    const schedule = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => scrollFocusedFieldIntoView(body), FOCUS_SCROLL_SETTLE_MS);
    };

    body.addEventListener("focusin", schedule);
    window.visualViewport?.addEventListener("resize", schedule);
    return () => {
      window.clearTimeout(timer);
      body.removeEventListener("focusin", schedule);
      window.visualViewport?.removeEventListener("resize", schedule);
    };
  }, [open, isCompact, body]);

  const nestedInset = depth > 0 ? NESTED_INSET_PX : 0;

  // Geometria vai em `style`, não em classe: inline vence qualquer ordenação de
  // variante do Tailwind e qualquer surpresa do tailwind-merge sobre `translate`.
  const compactStyle = {
    top: `calc(var(${CSS_VAR_OFFSET_TOP}, 0px) + ${nestedInset}px)`,
    left: 0,
    right: 0,
    width: "100%",
    maxWidth: "none",
    height: `calc(var(${CSS_VAR_HEIGHT}, 100dvh) - ${nestedInset}px)`,
    maxHeight: `calc(var(${CSS_VAR_HEIGHT}, 100dvh) - ${nestedInset}px)`,
    // As DUAS: o Tailwind 4 emite `-translate-x-1/2`/`-translate-y-1/2` pela propriedade
    // autônoma `translate`, que `transform: none` NÃO cancela. Sobrando, o dialog full-bleed
    // anda metade da própria largura pra esquerda e metade da altura pra cima — some da tela.
    transform: "none",
    translate: "none",
    borderRadius: nestedInset ? "var(--radius) var(--radius) 0 0" : "0px",
    paddingLeft: "env(safe-area-inset-left)",
    paddingRight: "env(safe-area-inset-right)",
    // `zoom-in-95` numa folha full-bleed lê como "encolheu". Troca por slide sem
    // mexer em classe: o tw-animate-css lê estas vars.
    "--tw-enter-scale": "1",
    "--tw-exit-scale": "1",
    "--tw-enter-translate-y": "1rem",
    "--tw-exit-translate-y": "1rem",
  } as React.CSSProperties;

  const wideStyle: React.CSSProperties = {
    // O 85vh histórico, mas capado pela área realmente visível: cobre desktop com
    // teclado virtual (2-in-1) sem mudar nada no caso comum.
    maxHeight: `min(85vh, calc(var(${CSS_VAR_HEIGHT}, 100vh) - 2rem))`,
  };

  const handleOpenChange = (next: boolean) => {
    if (busy || (!next && !dismissible)) return;
    // Solta o foco ANTES de desmontar: o iOS não fecha o teclado sozinho quando o
    // input focado sai do DOM, e a folha some deixando o teclado órfão na tela.
    if (!next) blurActiveElement();
    onOpenChange(next);
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    blurActiveElement();
    onSubmit?.(event);
  };

  const rows = (
    <>
      <div
        ref={setBody}
        data-slot="form-dialog-body"
        className={cn(
          // `min-h-0` é o que autoriza o flex a encolher. Sem ele o corpo empurra
          // o footer pra fora da tela e a regra inteira falha. NÃO REMOVER.
          // `overscroll-contain` mata o rubber-band do iOS no fim da lista.
          "min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 md:px-6",
          bodyClassName
        )}
      >
        {children}
      </div>

      {footer ? (
        <div
          data-slot="form-dialog-footer"
          className="flex shrink-0 flex-col-reverse gap-2 border-t px-4 pt-3 sm:flex-row sm:justify-end md:px-6"
          style={{ paddingBottom: "max(env(safe-area-inset-bottom), 0.75rem)" }}
        >
          {footer}
        </div>
      ) : null}
    </>
  );

  return (
    <FormDialogDepthContext value={depth + 1}>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent
          ref={contentRef}
          data-slot="form-dialog"
          data-keyboard-open={isKeyboardOpen ? "" : undefined}
          showCloseButton={dismissible}
          style={isCompact ? compactStyle : wideStyle}
          className={cn(
            // Sobrescreve o `grid gap-4 p-4` da base: as 3 faixas são o layout.
            "flex flex-col gap-0 overflow-hidden p-0",
            !isCompact && SIZE_CLASS[size],
            className
          )}
          onOpenAutoFocus={(event) => {
            // Mobile: focar um campo aqui sobe o teclado POR CIMA da animação de
            // abertura, e o iOS desloca a visual viewport no meio dela — o dialog
            // "pula". O foco vai pro container (o trap precisa de foco dentro) e o
            // usuário decide quando digitar. Atenção: `autoFocus` num <Input> é
            // uma SEGUNDA fonte de foco (o React chama .focus() sozinho) e precisa
            // ser removido do call site.
            if (!isCompact) return;
            event.preventDefault();
            contentRef.current?.focus();
          }}
          onEscapeKeyDown={(event) => {
            if (busy || !dismissible) event.preventDefault();
          }}
          onInteractOutside={(event) => {
            if (busy || !dismissible || !closeOnOutsideClick) event.preventDefault();
          }}
        >
          <DialogHeader
            className="shrink-0 border-b px-4 pt-3 pr-12 pb-3 md:px-6 md:pt-4 md:pb-4"
            style={
              isCompact ? { paddingTop: "calc(env(safe-area-inset-top) + 0.75rem)" } : undefined
            }
          >
            <DialogTitle>{title}</DialogTitle>
            {description ? (
              // Com teclado aberto em landscape sobra ~120px de corpo: a descrição
              // é a primeira coisa a sair. `sr-only` em vez de desmontar, pra não
              // deixar o `aria-describedby` do Radix pendurado.
              <DialogDescription className={cn(isKeyboardOpen && "sr-only")}>
                {description}
              </DialogDescription>
            ) : null}
          </DialogHeader>

          {onSubmit ? (
            <form className="flex min-h-0 flex-1 flex-col" onSubmit={handleSubmit} noValidate>
              {rows}
            </form>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col">{rows}</div>
          )}
        </DialogContent>
      </Dialog>
    </FormDialogDepthContext>
  );
}
