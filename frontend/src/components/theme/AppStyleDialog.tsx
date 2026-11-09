import { AppStylePreview } from "@/components/theme/AppStylePreview";
import { AppStyleSamples } from "@/components/theme/AppStyleSamples";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormDialog } from "@/components/ui/form-dialog";
import { useAppStyle, useAppStyleChoicePending, useFontSize } from "@/hooks/useAppStyle";
import { APP_STYLES, type AppStyleId, type AppStyleMode } from "@/lib/appearance/app-styles";
import { FONT_SIZES, type FontSizeId } from "@/lib/appearance/font-size";
import { cn } from "@/lib/utils";
import { CheckIcon, EyeIcon } from "@phosphor-icons/react";

const STYLE_GROUPS: ReadonlyArray<{ mode: AppStyleMode; label: string }> = [
  { mode: "light", label: "Claros" },
  { mode: "dark", label: "Escuros" },
];

/** Each button's "A" grows with the option, so it can be picked even without reading the name. */
const FONT_SIZE_GLYPH: Record<FontSizeId, string> = {
  padrao: "text-sm",
  grande: "text-lg",
  "muito-grande": "text-2xl",
};

const OPTION_CLASS = "hover:bg-accent min-w-0 rounded-lg border transition-colors";
const OPTION_SELECTED_CLASS = "border-primary ring-primary/30 bg-accent ring-2";
const GROUP_LABEL_CLASS = "text-muted-foreground text-xs font-medium";

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
 * Appearance settings, laid out like Shadcn Create (user decision 2026-11-09): the options sit on
 * the left and the right side labels itself as an example, so nobody mistakes those buttons for
 * real ones.
 *
 * Each tap applies at once to the whole app (this dialog included) without saving; "Salvar", or
 * closing, which keeps what is on screen, saves to the account.
 */
export function AppStyleDialog({ open, onOpenChange }: AppStyleDialogProps) {
  const { style, chooseStyle, previewStyle } = useAppStyle();
  const { fontSize, previewFontSize } = useFontSize();
  const confirmAppearance = () => {
    chooseStyle(style, fontSize);
    onOpenChange(false);
  };

  return (
    // `FormDialog` (header/body/footer anchored to the visual viewport): on a phone the body
    // scrolls and "Salvar" always stays in view. The two columns switch on the dialog's own width
    // (`@3xl`, in rem), so a large font size falls back to one column before anything gets tight.
    <FormDialog
      open={open}
      onOpenChange={(next) => !next && confirmAppearance()}
      size="2xl"
      className="h-[calc(100dvh-2rem)]"
      bodyClassName="@3xl:overflow-hidden @3xl:p-0"
      title="Aparência"
      description="Toque em uma opção e veja o app mudar na hora. Dá para trocar quando quiser no ícone de paleta, no topo da tela."
      footer={
        <Button onClick={confirmAppearance}>
          <CheckIcon aria-hidden />
          Salvar
        </Button>
      }
    >
      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 @3xl:h-full @3xl:grid-cols-[18rem_minmax(0,1fr)] @3xl:gap-0">
        <div className="space-y-4 @3xl:overflow-y-auto @3xl:overscroll-contain @3xl:border-r @3xl:p-4">
          <FontSizeOptions selected={fontSize} onSelect={previewFontSize} />
          <AppStyleOptions selected={style} onSelect={previewStyle} />
        </div>
        <AppearanceExample styleId={style} />
      </div>
    </FormDialog>
  );
}

function FontSizeOptions({
  selected,
  onSelect,
}: {
  selected: FontSizeId;
  onSelect: (id: FontSizeId) => void;
}) {
  return (
    <div role="radiogroup" aria-label="Tamanho da letra" className="space-y-1.5">
      <p className={GROUP_LABEL_CLASS}>Tamanho da letra</p>
      <div className="grid grid-cols-[repeat(3,minmax(0,1fr))] gap-1.5">
        {FONT_SIZES.map((item) => (
          <button
            key={item.id}
            type="button"
            role="radio"
            aria-checked={item.id === selected}
            onClick={() => onSelect(item.id)}
            className={cn(
              OPTION_CLASS,
              "flex min-h-16 flex-col items-center justify-center gap-1 px-1 py-1.5 text-center text-xs",
              item.id === selected && OPTION_SELECTED_CLASS
            )}
          >
            <span aria-hidden className={cn("leading-none font-bold", FONT_SIZE_GLYPH[item.id])}>
              A
            </span>
            <span className="leading-tight">{item.name}</span>
          </button>
        ))}
      </div>
    </div>
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
          <p className={GROUP_LABEL_CLASS}>{group.label}</p>
          <div className="grid grid-cols-[repeat(2,minmax(0,1fr))] gap-1.5 @3xl:grid-cols-1">
            {APP_STYLES.filter((item) => item.mode === group.mode).map((item) => (
              <button
                key={item.id}
                type="button"
                role="radio"
                aria-checked={item.id === selected}
                onClick={() => onSelect(item.id)}
                className={cn(
                  OPTION_CLASS,
                  "flex min-h-11 items-center gap-2 px-2.5 text-left text-sm md:min-h-10 @md:gap-3",
                  item.id === selected && OPTION_SELECTED_CLASS
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
 * Display-only area. `inert` removes focus and clicks from everything inside: otherwise Tab would
 * wander through fake buttons and people would think something needs configuring there.
 */
function AppearanceExample({ styleId }: { styleId: AppStyleId }) {
  return (
    <section
      aria-label="Exemplo de como o app fica"
      className="bg-muted/40 min-w-0 space-y-3 rounded-xl border p-3 @3xl:overflow-y-auto @3xl:overscroll-contain @3xl:rounded-none @3xl:border-0 @3xl:p-4"
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Badge variant="outline" className="bg-background">
          <EyeIcon aria-hidden />
          Exemplo
        </Badge>
        <p className="text-muted-foreground text-xs">
          Só para você ver como fica. Nada aqui funciona de verdade.
        </p>
      </div>
      <div inert className="space-y-3">
        <AppStylePreview styleId={styleId} />
        <AppStyleSamples />
      </div>
    </section>
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
