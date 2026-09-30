import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { memo } from "react";
import type { ActionConfirmationData } from "./types";

const STATUS_STYLES = {
  success: {
    container:
      "border-emerald-200 bg-emerald-50/50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/20 dark:text-emerald-100",
    icon: CheckCircle2,
    iconClass: "text-emerald-600 dark:text-emerald-400",
  },
  error: {
    container:
      "border-rose-200 bg-rose-50/50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/20 dark:text-rose-100",
    icon: AlertTriangle,
    iconClass: "text-rose-600 dark:text-rose-400",
  },
} as const;

/** Confirmation card for a tool that performed (or failed to perform) an action. */
export const ActionConfirmationResult = memo(function ActionConfirmationResult({
  data,
}: {
  data: ActionConfirmationData;
}) {
  const style = STATUS_STYLES[data.status] ?? STATUS_STYLES.error;
  const Icon = style.icon;

  return (
    <Card className={cn("my-3 w-full max-w-xl border", style.container)}>
      <CardContent className="flex gap-3 p-3">
        <Icon className={cn("size-5 shrink-0", style.iconClass)} />
        <p className="min-w-0 flex-1 text-sm leading-snug">{data.message}</p>
      </CardContent>
    </Card>
  );
});
