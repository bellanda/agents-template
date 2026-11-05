/**
 * Merges the per-test JSON parts into `test-results/visual/report.json` + `report.md`.
 * Run by `bun run qa:visual` after Playwright (pass or fail). No dependencies.
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";

const DIR = "test-results/visual";
const PARTS = `${DIR}/_parts`;

interface Finding {
  routeId: string;
  viewport: string;
  severity: "hard" | "warn";
  kind: string;
  selector: string;
  detail: string;
}

const findings: Finding[] = existsSync(PARTS)
  ? readdirSync(PARTS)
      .filter((file) => file.endsWith(".json"))
      .sort()
      .flatMap((file) => JSON.parse(readFileSync(`${PARTS}/${file}`, "utf8")) as Finding[])
  : [];

// First run with zero executed tests: the folder does not exist yet.
mkdirSync(DIR, { recursive: true });
writeFileSync(`${DIR}/report.json`, JSON.stringify(findings, null, 2));

const hard = findings.filter((f) => f.severity === "hard");
const warn = findings.filter((f) => f.severity === "warn");
const lines = [
  "# Visual QA report",
  "",
  `${hard.length} hard, ${warn.length} warnings. Screenshots: \`${DIR}/<route-id>/<viewport>.png\``,
];
for (const [title, list] of [
  ["Hard (fail)", hard],
  ["Warnings", warn],
] as const) {
  lines.push("", `## ${title}`, "");
  if (list.length === 0) lines.push("none");
  // Same kind+selector+viewport on many routes = shell chrome: one line with the route list.
  const groups = new Map<string, Finding[]>();
  for (const f of list) {
    const key = `${f.viewport}|${f.kind}|${f.selector}`;
    groups.set(key, [...(groups.get(key) ?? []), f]);
  }
  for (const group of groups.values()) {
    const first = group[0];
    const where =
      group.length > 1
        ? `${group.length} routes (${group.map((f) => f.routeId).join(", ")})`
        : `\`${first.routeId}\``;
    lines.push(
      `- ${where} / ${first.viewport} / **${first.kind}** \`${first.selector}\` - ${first.detail}`
    );
  }
}
writeFileSync(`${DIR}/report.md`, lines.join("\n") + "\n");
console.log(`visual QA: ${hard.length} hard, ${warn.length} warnings -> ${DIR}/report.md`);
