// Append to `src/lib/utils/dates.ts` (the ONLY place allowed to do calendar math by hand; guarded
// by `src/test/__tests__/timezone-guard.test.ts`). Incident 2026-11-05: `toISOString().slice(0,
// 10)` gave TOMORROW as "today" from 21:00 to 24:00 in São Paulo. Central source:
// Config Files/agents/skills/frontend/references/local-time/dates-local-day.ts.

const DATE_KEY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Local calendar day as `YYYY-MM-DD` (`<input type="date">` value, period params). */
export function toLocalDateKey(date: Date = new Date()): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** `YYYY-MM-DD` → Date at LOCAL midnight. The Date constructor parses a date-only string as UTC
 * midnight, which is the previous day in São Paulo. Throws on a malformed key: it is a
 * programming error, not user input. */
export function parseLocalDateKey(key: string): Date {
  const match = DATE_KEY_PATTERN.exec(key);
  if (!match) throw new Error(`invalid date key: received ${JSON.stringify(key)}, expected YYYY-MM-DD`);
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

/** Calendar-day arithmetic on a `YYYY-MM-DD` key (local calendar, safe across DST). */
export function addDaysToDateKey(key: string, days: number): string {
  const date = parseLocalDateKey(key);
  date.setDate(date.getDate() + days);
  return toLocalDateKey(date);
}
