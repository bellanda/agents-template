// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Guard (incident 2026-11-05): a calendar DAY in the browser is the LOCAL day of the user.
 * `new Date().toISOString().slice(0, 10)` is the UTC day, already TOMORROW from 21:00 to 24:00 in
 * São Paulo: "today" in a period filter or the `max` of a date input jumps a day at night.
 * `new Date("2026-11-05")` parses as UTC midnight and displays as the PREVIOUS day. Manual
 * `getTimezoneOffset()` math and `getUTC*()` live only inside `lib/utils/dates.ts`. Use
 * `toLocalDateKey`, `parseLocalDateKey`, `addDaysToDateKey`, `utcToDateTimeLocal` /
 * `dateTimeLocalToUtc`. A correct line carries `tz-ok: <why>` in a comment on that line.
 * Central source, copied unedited to every app: Config Files/agents/skills/frontend/references/
 * local-time/timezone-guard.test.ts.
 */
const SRC = join(__dirname, "..", "..");
const HELPERS_FILE = join("lib", "utils", "dates.ts");
const OK_MARKER = /tz-ok:\s*\S/;
const UTC_DAY_STRING =
  /\.toISOString\(\)\s*\.\s*(?:(?:slice|substring|substr)\(\s*0\s*,\s*10\s*\)|split\(\s*["'`]T["'`]\s*\))/;
const DATE_ONLY_PARSE = /(?:new Date|Date\.parse)\(\s*["'`]\d{4}-\d{2}-\d{2}["'`]\s*\)/;
const MANUAL_ZONE_MATH = /getTimezoneOffset\(|\.getUTC(?:FullYear|Month|Date|Day|Hours)\(/;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      return name === "__tests__" || name === "test" ? [] : sourceFiles(path);
    }
    return /\.tsx?$/.test(path) && !/\.test\.tsx?$/.test(path) ? [path] : [];
  });
}

function lineViolation(line: string, file: string): string | null {
  if (OK_MARKER.test(line)) return null;
  if (UTC_DAY_STRING.test(line)) return "toISOString() day is the UTC day; use toLocalDateKey()";
  if (DATE_ONLY_PARSE.test(line)) return "date-only string parses as UTC midnight";
  if (MANUAL_ZONE_MATH.test(line) && !file.endsWith(sep + HELPERS_FILE)) {
    return "manual offset/UTC calendar math belongs in lib/utils/dates.ts";
  }
  return null;
}

describe("calendar day in the browser", () => {
  it("never derives a day from the UTC clock", () => {
    const offenders = sourceFiles(SRC).flatMap((file) =>
      readFileSync(file, "utf8")
        .split("\n")
        .flatMap((line, index) => {
          const reason = lineViolation(line, file);
          return reason ? [`${relative(SRC, file)}:${index + 1}: ${reason}`] : [];
        })
    );
    expect(offenders).toEqual([]);
  });
});
