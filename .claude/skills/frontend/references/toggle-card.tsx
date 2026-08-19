// ToggleCard — canonical source (reference do gate frontend, item 8a).
// Vendored por projeto em frontend/src/components/ui/toggle-card.tsx.
// Requer os keyframes tc-wash-a / tc-wash-b / tc-beam / tc-dot no CSS global
// (bloco @theme — ver references/toggle-card.md).
import { cn } from "@/lib/utils";
import type { ComponentType } from "react";

interface ToggleCardProps {
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  title: string;
  /** Rendered only when size="default". */
  description?: string;
  /** Rendered only when size="default". */
  icon?: ComponentType<{ className?: string }>;
  disabled?: boolean;
  /** Transient commit in flight: blocks interaction WITHOUT dimming or restarting
   * the wash/beam. Use for `isPending`/`saving` — passing those as `disabled` makes
   * every sibling card blink. */
  busy?: boolean;
  /** Chip label while on. */
  activeLabel?: string;
  /** Chip label while off. */
  inactiveLabel?: string;
  /** "compact" drops icon/description — for peer grids (e.g. Diário/Semanal/Mensal). */
  size?: "default" | "compact";
  /** Visually mark this toggle as critical/sensitive (red accent). */
  accent?: "primary" | "destructive";
  className?: string;
}

/** Boolean toggle rendered as a fully clickable card. Replaces the "small Switch
 * lost inside a wide card" anti-pattern: the whole surface is the control, and the
 * state reads from the status chip + liquid wash (narrow bands sweeping across) plus
 * a hairline border beam synced to the wash, instead of a distant tick. */
export function ToggleCard({
  checked,
  onCheckedChange,
  title,
  description,
  icon: Icon,
  disabled = false,
  busy = false,
  activeLabel = "Ativo",
  inactiveLabel = "Desativado",
  size = "default",
  accent = "primary",
  className,
}: ToggleCardProps) {
  const isPrimary = accent === "primary";

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-busy={busy || undefined}
      disabled={disabled || busy}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "bg-card relative min-h-11 w-full overflow-hidden rounded-lg border text-left select-none",
        "transition-all duration-200 outline-none",
        "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-2",
        size === "default" ? "p-4" : "px-3 py-2.5",
        checked
          ? isPrimary
            ? "border-primary/60 bg-primary/5"
            : "border-destructive/60 bg-destructive/5"
          : "border-border/70 bg-muted/50 hover:bg-muted/70",
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
        className
      )}
    >
      {checked && !disabled && (
        <>
          {/* Liquid wash: faixas estreitas varrendo o card (sweep-and-empty). */}
          <span
            aria-hidden
            className="animate-in fade-in pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit] duration-700"
          >
            <span
              className={cn(
                "animate-tc-wash-a absolute -top-[50%] -left-[50%] h-[200%] w-[45%] rounded-full blur-2xl will-change-transform motion-reduce:hidden",
                isPrimary ? "bg-primary/18" : "bg-destructive/18"
              )}
            />
            <span
              className={cn(
                "animate-tc-wash-b absolute -top-[50%] -right-[55%] h-[200%] w-[50%] rounded-full blur-2xl will-change-transform motion-reduce:hidden",
                isPrimary ? "bg-primary/12" : "bg-destructive/12"
              )}
            />
          </span>
          {/* Hairline border beam (técnica do Border Beam do MagicUI, CSS-only) sincronizado
              ao wash: 1 volta (6s) a cada 2 ciclos da onda (3s); brilho pulsa junto. */}
          <span
            aria-hidden
            className={cn(
              "animate-tc-beam pointer-events-none absolute top-0 left-0 h-[0.5px] w-14 rounded-full bg-gradient-to-r to-transparent will-change-transform motion-reduce:hidden",
              isPrimary ? "from-transparent via-primary" : "from-transparent via-destructive"
            )}
            style={{
              offsetPath:
                "rect(1px calc(100% - 1px) calc(100% - 1px) 1px round calc(var(--radius) - 1px))",
            }}
          />
        </>
      )}

      <span
        className={cn("relative flex gap-3", size === "default" ? "items-start" : "items-center")}
      >
        {Icon && size === "default" && (
          <Icon
            className={cn(
              "mt-0.5 size-5 shrink-0 transition-colors",
              checked ? (isPrimary ? "text-primary" : "text-destructive") : "text-muted-foreground"
            )}
          />
        )}
        <span className="min-w-0 flex-1 space-y-1">
          <span
            className={cn(
              "block text-sm leading-none font-medium transition-colors",
              checked ? "text-foreground" : "text-muted-foreground"
            )}
          >
            {title}
          </span>
          {description && size === "default" && (
            <span
              className={cn(
                "block text-xs leading-relaxed transition-colors",
                checked ? "text-muted-foreground" : "text-muted-foreground/70"
              )}
            >
              {description}
            </span>
          )}
        </span>
        <span
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 self-center rounded-full px-2 py-0.5",
            "text-[10px] font-medium tracking-wider uppercase transition-colors",
            checked
              ? isPrimary
                ? "bg-primary/10 text-primary"
                : "bg-destructive/10 text-destructive"
              : "bg-muted text-muted-foreground"
          )}
        >
          <span
            className={cn(
              "size-1.5 rounded-full transition-colors motion-reduce:animate-none",
              checked
                ? isPrimary
                  ? "animate-tc-dot bg-primary"
                  : "animate-tc-dot bg-destructive"
                : "bg-muted-foreground/50"
            )}
          />
          {checked ? activeLabel : inactiveLabel}
        </span>
      </span>
    </button>
  );
}
