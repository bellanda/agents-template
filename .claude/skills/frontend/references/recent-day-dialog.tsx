import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  mondayFirstColumn,
  recentDayFullLabel,
  recentDayKeys,
  recentDayMonthLabel,
} from "@/lib/utils/recent-day";
import { parseLocalDateKey } from "@/lib/utils/dates";

const WEEKDAY_HEADERS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

interface RecentDayDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  today: string;
  /** Day already applied by the filter; the calendar opens on today without one. */
  selectedDay?: string;
  onPick: (day: string) => void;
}

/**
 * One grid with the last 30 running days, so "sexta passada" is one click even across a month
 * change. No month navigation and no Apply button on purpose: older days are "Personalizado…".
 */
export function RecentDayDialog({
  open,
  onOpenChange,
  today,
  selectedDay,
  onPick,
}: RecentDayDialogProps) {
  const days = recentDayKeys(today);
  const activeDay = selectedDay ?? today;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Dia recente</DialogTitle>
          <DialogDescription>Escolha um dia dos últimos 30.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-7 gap-1">
          {WEEKDAY_HEADERS.map((weekday) => (
            <span key={weekday} className="text-muted-foreground text-center text-xs">
              {weekday}
            </span>
          ))}
          {days.map((day, index) => {
            const dayOfMonth = parseLocalDateKey(day).getDate();
            const isToday = day === today;
            const startsMonth = index === 0 || dayOfMonth === 1;
            return (
              <Button
                key={day}
                type="button"
                variant={day === activeDay ? "default" : "ghost"}
                aria-label={recentDayFullLabel(day)}
                aria-pressed={day === activeDay}
                autoFocus={day === activeDay}
                className="h-11 min-w-0 flex-col gap-0 p-0 tabular-nums"
                style={index === 0 ? { gridColumnStart: mondayFirstColumn(day) + 1 } : undefined}
                onClick={() => onPick(day)}
              >
                <span className="text-sm leading-none">{dayOfMonth}</span>
                {isToday || startsMonth ? (
                  <span className="text-[0.625rem] leading-tight font-normal">
                    {isToday ? "Hoje" : recentDayMonthLabel(day)}
                  </span>
                ) : null}
              </Button>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
