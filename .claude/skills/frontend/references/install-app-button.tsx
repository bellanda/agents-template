import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { useIsStandalone } from "@/hooks/useIsStandalone";
import {
  closeInstallInstructions,
  openInstallInstructions,
  promptNativeInstall,
  useInstallPromptState,
} from "@/lib/pwa/install-prompt";
import { isIosDevice } from "@/lib/pwa/platform";
import { LuDownload, LuShare, LuSquarePlus } from "react-icons/lu";

/**
 * Instalar o app na tela inicial — padrão da frota (decisão do usuário 2026-10-07): o item
 * mora SÓ no menu do usuário, no rodapé da sidebar, na área logada. Nunca no login nem na landing.
 *
 * - Android/desktop Chromium: dispara o prompt nativo capturado no boot.
 * - iPhone/iPad (inclui iPadOS "desktop"): não há prompt — abre o dialog com os passos.
 * - Instalado (standalone) ou navegador sem como instalar (sem prompt e não iOS): some.
 *
 * O dialog (`InstallInstructionsDialog`) fica FORA do dropdown do usuário: o item do menu
 * desmonta ao fechar o menu, e um dialog filho fechava junto. Quem hospeda o botão renderiza
 * o dialog uma vez ao lado.
 */
function useInstallAction(): { visible: boolean; install: () => void } {
  const isStandalone = useIsStandalone();
  const { deferredPrompt } = useInstallPromptState();
  const isIos = isIosDevice();
  const visible = !isStandalone && (isIos || deferredPrompt !== null);

  const install = () => {
    if (deferredPrompt) void promptNativeInstall();
    else openInstallInstructions();
  };
  return { visible, install };
}

export function InstallAppMenuItem() {
  const { visible, install } = useInstallAction();
  if (!visible) return null;
  return (
    <DropdownMenuItem onSelect={install}>
      <LuDownload className="mr-2 size-4" />
      <span>Instalar app</span>
    </DropdownMenuItem>
  );
}

export function InstallInstructionsDialog() {
  const { instructionsOpen } = useInstallPromptState();
  return (
    <Dialog open={instructionsOpen} onOpenChange={(open) => !open && closeInstallInstructions()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Instalar na Tela de Início</DialogTitle>
          <DialogDescription>
            No iPhone e no iPad a instalação é feita pelo Safari, em 3 passos.
          </DialogDescription>
        </DialogHeader>
        <ol className="space-y-3 text-sm">
          <li className="flex items-start gap-3">
            <LuShare className="mt-0.5 size-5 shrink-0" />
            <span>
              Toque em <strong>Compartilhar</strong> na barra do Safari.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <LuSquarePlus className="mt-0.5 size-5 shrink-0" />
            <span>
              Escolha <strong>Adicionar à Tela de Início</strong>.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <LuDownload className="mt-0.5 size-5 shrink-0" />
            <span>
              Confirme em <strong>Adicionar</strong> e abra o app pelo novo ícone.
            </span>
          </li>
        </ol>
        <p className="text-muted-foreground text-xs">
          Só funciona no Safari (outros navegadores do iPhone não instalam apps).
        </p>
      </DialogContent>
    </Dialog>
  );
}
