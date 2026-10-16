import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";

interface UpdateBannerProps {
  /** Segundos até recarregar; `null` = sem contagem (anti-loop acionado: só o botão). */
  secondsLeft: number | null;
  onUpdate: () => void;
}

/**
 * Aviso de versão nova (decisão 2026-10-16). Fixo no rodapé, acima do home indicator do iOS
 * (safe-area). `role="status"` de propósito — NÃO `dialog`, senão pausaria a própria contagem.
 */
export function UpdateBanner({ secondsLeft, onUpdate }: UpdateBannerProps) {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[100] flex justify-center px-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
      <div
        role="status"
        aria-live="polite"
        className="bg-card text-card-foreground pointer-events-auto flex w-full max-w-md items-center gap-3 rounded-lg border p-3 shadow-lg"
      >
        <RefreshCw className="text-primary size-4 shrink-0" aria-hidden />
        <p className="min-w-0 flex-1 text-sm">
          {secondsLeft === null
            ? "Nova versão disponível"
            : `Nova versão disponível — atualizando em ${secondsLeft}s`}
        </p>
        <Button size="sm" onClick={onUpdate} className="shrink-0">
          Atualizar agora
        </Button>
      </div>
    </div>
  );
}
