import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, X } from "lucide-react";

interface PermissionSearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}

/**
 * Busca das abas de funções/permissões. Rascunho efêmero do dialog (`useState` no pai), não estado
 * de tela de coleção — sem URL, sem debounce: o catálogo já veio inteiro e o filtro é client-side.
 *
 * A fonte vem do `Input` (`text-base md:text-sm`) e NÃO pode ser reduzida aqui: campo nativo abaixo
 * de 16px no celular dispara o auto-zoom do iOS e o dialog `position: fixed` some da tela.
 */
export function PermissionSearchInput({
  value,
  onChange,
  placeholder,
}: PermissionSearchInputProps) {
  return (
    <div className="relative shrink-0">
      <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="pr-9 pl-9"
      />
      {value ? (
        <Button
          variant="ghost"
          size="icon"
          className="absolute top-1/2 right-1 size-7 -translate-y-1/2"
          onClick={() => onChange("")}
          aria-label="Limpar busca"
        >
          <X className="size-4" />
        </Button>
      ) : null}
    </div>
  );
}
