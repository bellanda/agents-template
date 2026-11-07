import { AppStylePreview } from "@/components/theme/AppStylePreview";
import { Button } from "@/components/ui/button";
import { FormDialog } from "@/components/ui/form-dialog";
import { useAppStyle, useAppStyleChoicePending } from "@/hooks/useAppStyle";
import {
  APP_STYLES,
  findAppStyle,
  type AppStyleId,
  type AppStyleMode,
} from "@/lib/appearance/app-styles";
import { cn } from "@/lib/utils";
import { CheckIcon } from "@phosphor-icons/react";

const STYLE_GROUPS: ReadonlyArray<{ mode: AppStyleMode; label: string }> = [
  { mode: "light", label: "Claros" },
  { mode: "dark", label: "Escuros" },
];

/**
 * Primeira entrada na plataforma: abre sozinho uma vez por conta (`ui_preferences.app_style`
 * vazio). Monte SÓ na casca de trabalho — tela operacional em tela cheia, kiosk e rota pública
 * por token nunca abrem este dialog. Depois, o mesmo dialog volta pela paleta do header.
 */
export function AppStyleWelcomeDialog() {
  const isPending = useAppStyleChoicePending();
  // Fechar já grava a escolha, e é isso que tira `isPending` — nada a fazer aqui.
  return <AppStyleDialog open={isPending} onOpenChange={() => {}} />;
}

interface AppStyleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Escolha de estilo com prévia ao vivo.
 *
 * Cada toque aplica o estilo na hora ao app inteiro (este dialog incluso) e à prévia, sem
 * gravar; "Usar" — ou fechar, que fica com o que está na tela — grava na conta.
 */
export function AppStyleDialog({ open, onOpenChange }: AppStyleDialogProps) {
  const { style, chooseStyle, previewStyle } = useAppStyle();
  const confirmStyle = () => {
    chooseStyle(style);
    onOpenChange(false);
  };

  return (
    // `FormDialog` (header/body/footer anchored to the visual viewport): on a phone the body
    // scrolls and "Usar" always stays in view (a plain/sticky footer ended up off-screen or
    // floating over the list in QA, 2026-11-07). The list comes first so the choice is one tap
    // away on a phone; from @2xl the preview sits to the right of it.
    <FormDialog
      open={open}
      onOpenChange={(next) => !next && confirmStyle()}
      size="xl"
      title="Escolha o seu estilo"
      description="Toque em um estilo e veja o app mudar na hora. Dá para trocar quando quiser no ícone de paleta, no topo da tela."
      footer={
        <Button onClick={confirmStyle}>
          <CheckIcon aria-hidden />
          Usar {findAppStyle(style).name}
        </Button>
      }
    >
      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 @2xl:grid-cols-[15rem_minmax(0,1fr)]">
        <AppStyleOptions selected={style} onSelect={previewStyle} />
        <div className="min-w-0">
          <AppStylePreview styleId={style} />
        </div>
      </div>
    </FormDialog>
  );
}

function AppStyleOptions({
  selected,
  onSelect,
}: {
  selected: AppStyleId;
  onSelect: (id: AppStyleId) => void;
}) {
  return (
    <div role="radiogroup" aria-label="Estilos" className="space-y-3">
      {STYLE_GROUPS.map((group) => (
        <div key={group.mode} className="space-y-1.5">
          <p className="text-muted-foreground text-xs font-medium">{group.label}</p>
          <div className="grid grid-cols-[repeat(2,minmax(0,1fr))] gap-1.5 @2xl:grid-cols-1">
            {APP_STYLES.filter((item) => item.mode === group.mode).map((item) => (
              <button
                key={item.id}
                type="button"
                role="radio"
                aria-checked={item.id === selected}
                onClick={() => onSelect(item.id)}
                className={cn(
                  "hover:bg-accent flex min-h-11 min-w-0 items-center gap-2 rounded-lg border px-2.5 text-left text-sm transition-colors md:min-h-10 @md:gap-3",
                  item.id === selected && "border-primary ring-primary/30 bg-accent ring-2"
                )}
              >
                <AppStyleSwatch styleId={item.id} mode={item.mode} />
                <span className="leading-tight">{item.name}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Miniatura do estilo: sidebar, fundo e a primária. As cores saem do MESMO CSS do estilo
 * (`.light|.dark[data-style-preview="<id>"]` em `styles/themes/`), sem hex duplicado.
 */
function AppStyleSwatch({ styleId, mode }: { styleId: string; mode: AppStyleMode }) {
  return (
    <span
      aria-hidden
      data-style-preview={styleId}
      className={cn(
        mode,
        "border-border bg-background flex h-7 w-10 shrink-0 overflow-hidden rounded-md border"
      )}
    >
      <span className="bg-sidebar border-sidebar-border h-full w-3 border-r" />
      <span className="flex flex-1 flex-col justify-center gap-1 px-1">
        <span className="bg-primary h-1.5 w-4 rounded-full" />
        <span className="bg-muted-foreground/40 h-1 w-full rounded-full" />
      </span>
    </span>
  );
}
