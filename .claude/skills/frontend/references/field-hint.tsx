import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { LuCircleHelp } from "react-icons/lu";

interface Props {
  children: React.ReactNode;
  className?: string;
  side?: "top" | "right" | "bottom" | "left";
}

/** Ícone (?) que revela uma explicação CURTA e específica do campo.
 *
 * Fica ao lado da `<Label>`, e só para o que é do próprio campo — formato aceito,
 * unidade, faixa, efeito imediato do valor. "Para que serve" e "onde isso aparece"
 * são da explicação da tela (botão "Como funciona"), não daqui.
 *
 * É Popover e não Tooltip DE PROPÓSITO. O `Tooltip` do Radix implementa o padrão
 * WAI-ARIA de tooltip: abre no hover e no foco, e fecha no `pointerdown` — um
 * toque no gatilho significa "ativar o gatilho", não "ler a dica". No celular o
 * navegador emite `pointerdown` e `mouseenter` no MESMO gesto, então a dica
 * abria e fechava no mesmo toque e era impossível ler. Popover abre no clique,
 * que é o gesto disponível nos dois ambientes.
 *
 * ```tsx
 * <Label className="flex items-center gap-1.5">
 *   Fotos mínimas <FieldHint>Aceita de 1 a 20.</FieldHint>
 * </Label>
 * ```
 */
export function FieldHint({ children, className, side = "top" }: Props) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          tabIndex={0}
          aria-label="Ajuda"
          className={cn(
            "text-muted-foreground hover:text-foreground relative inline-flex h-4 w-4 items-center justify-center rounded-full transition-colors after:absolute after:-inset-2.5 focus-visible:ring-1 focus-visible:outline-none",
            className
          )}
        >
          <LuCircleHelp className="h-3.5 w-3.5" strokeWidth={1.75} />
        </button>
      </PopoverTrigger>
      <PopoverContent side={side} className="w-auto max-w-xs text-sm leading-relaxed">
        {children}
      </PopoverContent>
    </Popover>
  );
}
