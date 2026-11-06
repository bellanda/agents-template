import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
} from "@/components/ui/popover";
import { useAppStyleChoicePending } from "@/hooks/useAppStyle";
import { useDataProvider } from "@/lib/api/context";
import { authStore } from "@/lib/auth/auth-store";
import {
  getActiveBalloonMark,
  releaseBalloonSlot,
  requestBalloonSlot,
  subscribeBalloonSlot,
} from "@/components/onboarding/balloon-slot";
import { getSeenTopics, markTopicSeenLocally, mergeSeenTopics } from "@/lib/help/help-seen";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
  type RefObject,
} from "react";

const UI_PREFERENCES_ENDPOINT = "/accounts/me/ui-preferences";
/**
 * As marcas dos balões moram na MESMA lista do "já vi" das ajudas (`ui_preferences.help_seen`,
 * unida no servidor, sem migration), só com este prefixo para não colidir com tópico de ajuda.
 */
const BALLOON_MARK_PREFIX = "balloon:";

export interface OnboardingBalloonProps {
  /** Identidade estável do balão (vira a marca "visto" do usuário); ≤ 56 caracteres. */
  id: string;
  title: string;
  description: string;
  /** O elemento apontado (precisa aceitar `ref`). Sem filho, ancora no canto superior esquerdo do ancestral posicionado. */
  children?: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  /** `false` segura o balão (ex.: o alvo ainda não carregou). */
  enabled?: boolean;
}

/**
 * The same balloon is often mounted twice (desktop column + phone button, swapped by CSS): only the
 * copy that is actually rendered may open. `checkVisibility` is missing in jsdom and old Safari, so
 * there the copy counts as visible (worst case both open, as before this check).
 */
function isProbeRendered(probe: HTMLElement | null): boolean {
  if (!probe) return false;
  return typeof probe.checkVisibility === "function" ? probe.checkVisibility() : true;
}

/**
 * A modal Radix dialog marks everything outside it with `data-aria-hidden` (aria-hidden's
 * `hideOthers`). An anchor under a modal must not pop its balloon over the dialog: a deep link
 * (`?attendance=`) opened the list balloon on top of the detail dialog and it swallowed the taps.
 */
function isProbeBehindModal(probe: HTMLElement | null): boolean {
  return probe?.parentElement?.closest("[data-aria-hidden]") != null;
}

/** Live "behind a modal" flag, observed only while the balloon could open (cheap: one filter). */
function useIsBehindModal(probeRef: RefObject<HTMLElement | null>, isWatching: boolean): boolean {
  const [isBehind, setIsBehind] = useState(false);
  useEffect(() => {
    if (!isWatching) return;
    const update = () => setIsBehind(isProbeBehindModal(probeRef.current));
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ["data-aria-hidden"],
      subtree: true,
    });
    return () => observer.disconnect();
  }, [probeRef, isWatching]);
  return isWatching && isBehind;
}

/** Marca de um balão no servidor; exportada para os testes e para quem quiser reabrir um balão. */
export function balloonMark(id: string): string {
  return `${BALLOON_MARK_PREFIX}${id}`;
}

/**
 * Balão de onboarding do vendedor novo: popover ancorado que aparece UMA vez por usuário.
 * "Entendi" grava a marca no servidor (`PATCH /accounts/me/ui-preferences`, em background) e
 * no cache local; aparelho novo do mesmo usuário não repete. Não rouba foco nem trava a tela.
 *
 *     <OnboardingBalloon id="crm-lista" title="…" description="…">
 *       <Button>Alvo</Button>
 *     </OnboardingBalloon>
 */
export function OnboardingBalloon(props: OnboardingBalloonProps) {
  const { id, title, description, children, side = "bottom", enabled = true } = props;
  const { client } = useDataProvider();
  const isStyleChoicePending = useAppStyleChoicePending();
  const mark = balloonMark(id);
  const [dismissed, setDismissed] = useState(false);
  const [wasSeenBefore, setWasSeenBefore] = useState<boolean | null>(null);
  const [isRendered, setIsRendered] = useState(false);
  const probeRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    mergeSeenTopics(authStore.getState().user?.uiPreferences?.helpSeen);
    setWasSeenBefore(getSeenTopics().has(mark));
    setIsRendered(isProbeRendered(probeRef.current));
  }, [mark, enabled]);

  const dismiss = useCallback(() => {
    setDismissed(true);
    if (!markTopicSeenLocally(mark)) return;
    // Silencioso: falhar em gravar não é algo que o usuário resolva; no pior caso o balão volta.
    void client.patch(UI_PREFERENCES_ENDPOINT, { helpSeen: [mark] }).catch(() => {});
  }, [client, mark]);

  const couldOpen =
    enabled && isRendered && !isStyleChoicePending && wasSeenBefore === false && !dismissed;
  // Closing here is controlled (`open` flips), so it does NOT mark the balloon as seen: it comes
  // back when the dialog closes.
  const isBehindModal = useIsBehindModal(probeRef, couldOpen);
  const isEligible = couldOpen && !isBehindModal;
  useEffect(() => {
    if (!isEligible) return;
    requestBalloonSlot(mark);
    return () => releaseBalloonSlot(mark);
  }, [isEligible, mark]);
  const activeMark = useSyncExternalStore(
    subscribeBalloonSlot,
    getActiveBalloonMark,
    getActiveBalloonMark
  );
  const isOpen = isEligible && activeMark === mark;

  return (
    <>
      {/* Zero-size probe next to the anchor: tells whether this copy is on screen. */}
      <span ref={probeRef} aria-hidden className="sr-only" />
      <Popover open={isOpen} onOpenChange={(next) => !next && dismiss()}>
        {children ? (
          // Tapping the pointed control is "understood" too: on touch, Radix only dismisses on the
          // following click, after the control already opened its own dialog under the balloon.
          <PopoverAnchor asChild onClickCapture={isOpen ? dismiss : undefined}>
            {children}
          </PopoverAnchor>
        ) : (
          <PopoverAnchor className="pointer-events-none absolute top-0 left-6 size-0" />
        )}
        <PopoverContent
          side={side}
          className="w-72 gap-3 p-3"
          onOpenAutoFocus={(event) => event.preventDefault()}
          data-testid={`onboarding-balloon-${id}`}
        >
          <PopoverHeader>
            <PopoverTitle>{title}</PopoverTitle>
            <PopoverDescription>{description}</PopoverDescription>
          </PopoverHeader>
          <Button size="sm" className="self-end" onClick={dismiss}>
            Entendi
          </Button>
        </PopoverContent>
      </Popover>
    </>
  );
}
