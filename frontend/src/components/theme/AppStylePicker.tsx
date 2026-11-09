import { AppStyleDialog } from "@/components/theme/AppStyleDialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { PaletteIcon } from "@phosphor-icons/react";
import { useState } from "react";

/** Paleta do header: abre o mesmo dialog de aparência da primeira entrada, com a prévia. */
export function AppStylePicker({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        variant="outline"
        size="icon"
        className={cn("border-input bg-background hover:bg-accent", className)}
        title="Aparência"
        onClick={() => setOpen(true)}
      >
        <PaletteIcon className="size-5" />
        <span className="sr-only">Escolher aparência</span>
      </Button>
      <AppStyleDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
