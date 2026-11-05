/**
 * `bun run qa:visual [-- <playwright args>]`: runs the 3 visual projects, then merges the report.
 * Extra args go straight to Playwright, e.g. `bun run qa:visual -- --grep vehicle-sale`.
 * A run without `--grep`/`-g` clears old per-test parts; a filtered one keeps them, so the report
 * then mixes fresh findings for the filtered routes with the previous run's for the others.
 * Other args (`--workers=2`) do not count as a filter.
 */
import { spawnSync } from "node:child_process";
import { rmSync } from "node:fs";

const extraArgs = process.argv.slice(2);
const isFiltered = extraArgs.some((arg) => arg === "-g" || arg.startsWith("--grep"));
if (!isFiltered) rmSync("test-results/visual/_parts", { recursive: true, force: true });

const playwright = spawnSync(
  "bunx",
  [
    "playwright",
    "test",
    "--project=visual-mobile",
    "--project=visual-tablet",
    "--project=visual-desktop",
    ...extraArgs,
  ],
  { stdio: "inherit" }
);
spawnSync("bun", ["e2e/visual/build-report.ts"], { stdio: "inherit" });
process.exit(playwright.status ?? 1);
