/**
 * "Dia recente" of the central date filter (user decision 2026-11-09): one calendar with the last
 * 30 running days, whatever month they fall in, ending today. Canonical copy for the fleet:
 * Config Files/agents/skills/frontend/references/dashboard-kpi.md.
 *
 * Works on local day keys (`YYYY-MM-DD`), which compare correctly as plain strings.
 */
import { addDaysToDateKey, parseLocalDateKey } from "@/lib/utils/dates";

export const RECENT_DAY_COUNT = 30;

/** The selectable days, oldest first, `today` last. */
export function recentDayKeys(today: string): string[] {
  return Array.from({ length: RECENT_DAY_COUNT }, (_, index) =>
    addDaysToDateKey(today, index - RECENT_DAY_COUNT + 1)
  );
}

export function isRecentDay(day: string, today: string): boolean {
  return day <= today && day >= addDaysToDateKey(today, 1 - RECENT_DAY_COUNT);
}

/** Calendar column of a day, Monday first: the same week start as the "Semana" preset. */
export function mondayFirstColumn(day: string): number {
  return (parseLocalDateKey(day).getDay() + 6) % 7;
}

const TRIGGER_FORMAT = new Intl.DateTimeFormat("pt-BR", {
  weekday: "short",
  day: "2-digit",
  month: "2-digit",
});
const FULL_FORMAT = new Intl.DateTimeFormat("pt-BR", {
  weekday: "long",
  day: "numeric",
  month: "long",
});
const MONTH_FORMAT = new Intl.DateTimeFormat("pt-BR", { month: "short" });

/** "sex., 06/11": what the filter shows after a day is picked. */
export function recentDayLabel(day: string): string {
  return TRIGGER_FORMAT.format(parseLocalDateKey(day));
}

/** "sexta-feira, 6 de novembro": screen-reader name of a calendar cell. */
export function recentDayFullLabel(day: string): string {
  return FULL_FORMAT.format(parseLocalDateKey(day));
}

/** "nov": marks where a month starts, because the grid runs across months without a title. */
export function recentDayMonthLabel(day: string): string {
  return MONTH_FORMAT.format(parseLocalDateKey(day)).replace(".", "");
}
