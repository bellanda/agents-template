/**
 * Pure helpers behind the grouped business-hours editor (fleet standard, gate `frontend` ->
 * `references/business-hours-editor.md`).
 *
 * The stored shape stays one `{ closed, slots }` entry per weekday (backend contract, never
 * changes). "Groups" ("Seg a Sex: 11:30-14:00 e 19:00-21:45") are a UI-only view: `groupHours`
 * derives them from the stored map and `ungroupHours` writes them back. Keep this file free of
 * React and app-specific imports so it can be copied verbatim between apps.
 */
import type { BusinessHourSlot, BusinessHoursDay, WeekdayKey } from "@/lib/api/services/branding";

export type HoursMap = Partial<Record<WeekdayKey, BusinessHoursDay>>;

/** One schedule applied to several weekdays. Only open schedules form groups; every weekday that
 * is in no group is closed. */
export interface HoursGroup {
  id: number;
  days: WeekdayKey[];
  slots: BusinessHourSlot[];
}

export const WEEKDAYS: { key: WeekdayKey; label: string; short: string }[] = [
  { key: "mon", label: "Segunda", short: "Seg" },
  { key: "tue", label: "Terça", short: "Ter" },
  { key: "wed", label: "Quarta", short: "Qua" },
  { key: "thu", label: "Quinta", short: "Qui" },
  { key: "fri", label: "Sexta", short: "Sex" },
  { key: "sat", label: "Sábado", short: "Sáb" },
  { key: "sun", label: "Domingo", short: "Dom" },
];

export const WEEKDAY_PRESETS: { id: string; label: string; days: WeekdayKey[] }[] = [
  { id: "weekdays", label: "Seg–Sex", days: ["mon", "tue", "wed", "thu", "fri"] },
  { id: "weekend", label: "Fim de semana", days: ["sat", "sun"] },
  { id: "all", label: "Todos os dias", days: WEEKDAYS.map((day) => day.key) },
];

export const DEFAULT_SLOT: BusinessHourSlot = { open: "09:00", close: "18:00" };
const HHMM_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

export function cloneSlots(slots: BusinessHourSlot[]): BusinessHourSlot[] {
  return slots.map((slot) => ({ ...slot }));
}

/** Slots in chronological order, so "19:00-21:45 + 11:30-14:00" equals "11:30-14:00 + 19:00-21:45". */
function sortedSlots(slots: BusinessHourSlot[]): BusinessHourSlot[] {
  return [...slots].sort((a, b) => a.open.localeCompare(b.open) || a.close.localeCompare(b.close));
}

function scheduleKey(slots: BusinessHourSlot[]): string {
  return sortedSlots(slots)
    .map((slot) => `${slot.open}-${slot.close}`)
    .join("|");
}

/** Open day with no stored slot is treated as closed: there is nothing to show or schedule. */
function isOpenDay(day: BusinessHoursDay | undefined): day is BusinessHoursDay {
  return !!day && !day.closed && day.slots.length > 0;
}

/** Derives the groups from stored hours: days with identical slots share one group, in
 * first-appearance (Monday-first) order. Closed days belong to no group. */
export function groupHours(hours: HoursMap): HoursGroup[] {
  const byKey = new Map<string, HoursGroup>();
  for (const { key } of WEEKDAYS) {
    const day = hours[key];
    if (!isOpenDay(day)) continue;
    const id = scheduleKey(day.slots);
    const group = byKey.get(id);
    if (group) group.days.push(key);
    else byKey.set(id, { id: byKey.size, days: [key], slots: cloneSlots(day.slots) });
  }
  return [...byKey.values()];
}

/** Writes groups back to the stored per-weekday shape (all 7 keys; ungrouped = closed). A day in
 * two groups keeps the LAST one, so a stale draft can never emit conflicting data. */
export function ungroupHours(groups: HoursGroup[]): HoursMap {
  const hours: HoursMap = {};
  for (const { key } of WEEKDAYS) hours[key] = { closed: true, slots: [] };
  for (const group of groups) {
    for (const key of group.days) hours[key] = { closed: false, slots: cloneSlots(group.slots) };
  }
  return hours;
}

/** Semantic equality of two stored maps (missing day == closed day, slot order ignored). */
export function hoursEqual(a: HoursMap, b: HoursMap): boolean {
  return WEEKDAYS.every(({ key }) => {
    const left = a[key];
    const right = b[key];
    if (!isOpenDay(left) || !isOpenDay(right)) return isOpenDay(left) === isOpenDay(right);
    return scheduleKey(left.slots) === scheduleKey(right.slots);
  });
}

/** Puts `days` in the group `groupId`, taking them away from any other group. Groups left with
 * no days are dropped, except the edited one (an empty draft group stays so the user can fill it). */
export function assignDays(
  groups: HoursGroup[],
  groupId: number,
  days: WeekdayKey[]
): HoursGroup[] {
  const claimed = new Set(days);
  return groups
    .map((group) =>
      group.id === groupId
        ? { ...group, days: WEEKDAYS.filter((d) => claimed.has(d.key)).map((d) => d.key) }
        : { ...group, days: group.days.filter((key) => !claimed.has(key)) }
    )
    .filter((group) => group.id === groupId || group.days.length > 0);
}

/** Moves a single weekday into `groupId` (or closes it when it is already there). */
export function toggleDayInGroup(
  groups: HoursGroup[],
  groupId: number,
  day: WeekdayKey
): HoursGroup[] {
  const target = groups.find((group) => group.id === groupId);
  if (!target) return groups;
  const days = target.days.includes(day)
    ? target.days.filter((key) => key !== day)
    : [...target.days, day];
  return assignDays(groups, groupId, days);
}

/** New empty group (no days yet) with a sensible default schedule. */
export function addGroup(groups: HoursGroup[]): HoursGroup[] {
  const id = groups.reduce((max, group) => Math.max(max, group.id), -1) + 1;
  return [...groups, { id, days: [], slots: [{ ...DEFAULT_SLOT }] }];
}

/** Weekdays that belong to no group (closed). */
export function closedDays(groups: HoursGroup[]): WeekdayKey[] {
  const open = new Set(groups.flatMap((group) => group.days));
  return WEEKDAYS.map((day) => day.key).filter((key) => !open.has(key));
}

/** "Copy from another day": the schedule of `from` as a fresh slots array, or null if it is closed. */
export function slotsFromDay(hours: HoursMap, from: WeekdayKey): BusinessHourSlot[] | null {
  const day = hours[from];
  return isOpenDay(day) ? cloneSlots(day.slots) : null;
}

/** Compact title for a set of weekdays: "Seg a Sex", "Sáb e Dom", "Seg, Qua e Sex", "Segunda". */
export function formatDayRange(days: WeekdayKey[]): string {
  const order = WEEKDAYS.map((day) => day.key);
  const indexes = days.map((key) => order.indexOf(key)).sort((a, b) => a - b);
  if (indexes.length === 0) return "Nenhum dia";
  if (indexes.length === 1) return WEEKDAYS[indexes[0]].label;
  const runs: number[][] = [];
  for (const index of indexes) {
    const last = runs[runs.length - 1];
    if (last && index === last[last.length - 1] + 1) last.push(index);
    else runs.push([index]);
  }
  const parts = runs.map((run) =>
    run.length === 1
      ? WEEKDAYS[run[0]].short
      : `${WEEKDAYS[run[0]].short} ${run.length === 2 ? "e" : "a"} ${WEEKDAYS[run[run.length - 1]].short}`
  );
  if (parts.length === 1) return parts[0];
  // "Seg e Ter, Qui" reads better than "Seg e Ter e Qui" when a run already uses "e".
  if (runs.some((run) => run.length > 1)) return parts.join(", ");
  return `${parts.slice(0, -1).join(", ")} e ${parts[parts.length - 1]}`;
}

function toMinutes(time: string): number {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

/** pt-BR message for the first problem in a list of time ranges, or null when valid. */
export function validateSlots(slots: BusinessHourSlot[]): string | null {
  if (slots.length === 0) return "Informe ao menos um horário.";
  if (slots.some((slot) => !HHMM_RE.test(slot.open) || !HHMM_RE.test(slot.close))) {
    return "Preencha abertura e fechamento de todos os horários.";
  }
  if (slots.some((slot) => toMinutes(slot.close) <= toMinutes(slot.open))) {
    return "O fechamento deve ser depois da abertura.";
  }
  const ordered = [...slots].sort((a, b) => toMinutes(a.open) - toMinutes(b.open));
  for (let i = 1; i < ordered.length; i++) {
    if (toMinutes(ordered[i].open) < toMinutes(ordered[i - 1].close)) {
      return "Os horários deste grupo se sobrepõem.";
    }
  }
  return null;
}

/** First problem across all groups ("Seg a Sex: …"), or null. Lets a parent block saving. */
export function validateGroups(groups: HoursGroup[]): string | null {
  for (const group of groups) {
    if (group.days.length === 0) return "Escolha ao menos um dia em cada grupo de horário.";
    const problem = validateSlots(group.slots);
    if (problem) return `${formatDayRange(group.days)}: ${problem}`;
  }
  return null;
}

/** Same check straight on a stored map (what a parent holds), for blocking "Salvar". Days with
 * identical slots are one group, so the message names the weekdays that share the bad schedule. */
export function validateHoursMap(hours: HoursMap): string | null {
  return validateGroups(groupHours(hours));
}
