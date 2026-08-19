// Cross-project standard (gate frontend, ref toggle-card.md). Requires the
// `tc-beam` / `tc-dot` keyframes in the global CSS.
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
   * the beam. Use for `isPending`/`saving` — passing those as `disabled` makes
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
 * state reads from the status chip + orbit beam instead of a distant tick. */
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
        <span
          aria-hidden
          className="animate-in fade-in pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit] duration-700"
        >
          {/* MagicUI-style border beam orbiting the card edge (offset-path comet). */}
          <span
            className={cn(
              "animate-tc-beam absolute h-3 w-16 blur-[1px] [offset-path:rect(0_auto_auto_0_round_var(--radius,0.5rem))] motion-reduce:hidden",
              isPrimary
                ? "from-primary via-primary/50 bg-gradient-to-l to-transparent"
                : "from-destructive via-destructive/50 bg-gradient-to-l to-transparent"
            )}
          />
        </span>
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
