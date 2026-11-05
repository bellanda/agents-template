/**
 * Snippet to merge into the app's `frontend/playwright.config.ts` (canonical: kailos, 2026-11-05).
 * 1. Add the type imports below to the existing `@playwright/test` import.
 * 2. Paste `VISUAL_GLOB` + `VISUAL_LOCALE` near the other constants (keep `DEV_PORT`/`LIVE`/`BASE_URL`
 *    from the app's config; `LIVE` = `process.env.E2E_LIVE === "1"`, never prod).
 * 3. Add `testIgnore: VISUAL_GLOB` to EVERY existing functional project, then append the 3 projects.
 *    Also set the top-level `outputDir: "test-results/.playwright"` (see the example below):
 *    Playwright wipes `outputDir` on every run, `--grep` included, so the default
 *    (`test-results`) would delete every route's screenshots and `_parts` (akmeo, 2026-11-05).
 * 4. package.json: `"qa:visual": "bun e2e/visual/run.ts"`.
 * 5. .gitignore already covers `test-results/` (check).
 */
import {
  defineConfig,
  devices,
  type PlaywrightTestOptions,
  type PlaywrightWorkerOptions,
} from "@playwright/test";

// Visual QA has its own opt-in projects (`bun run qa:visual`); the functional ones skip it.
const VISUAL_GLOB = "**/e2e/visual/**";
// The QA screenshots must look like the user's phone: pt-BR dates/times and native inputs
// ("dd/mm/aaaa", "18:00", not "mm/dd/yyyy", "06:00 PM") and the store's clock.
// `locale` covers Intl/navigator only. Native <input type="date|time"> follow the browser process
// locale: on Linux headless Chromium that is the LANG env (verified 2026-11-05: `--lang` alone still
// rendered "08:00 AM"; LANG=pt_BR.UTF-8 renders "18:00").
const VISUAL_LOCALE: Pick<
  PlaywrightTestOptions & PlaywrightWorkerOptions,
  "locale" | "timezoneId" | "launchOptions"
> = {
  locale: "pt-BR",
  timezoneId: "America/Sao_Paulo",
  launchOptions: {
    args: ["--lang=pt-BR"],
    env: { ...(process.env as Record<string, string>), LANG: "pt_BR.UTF-8", LANGUAGE: "pt_BR" },
  },
};

export const VISUAL_PROJECTS = [
  {
    name: "visual-mobile",
    testMatch: "**/e2e/visual/**/*.spec.ts",
    // iPhone 15 (390x844, DPR 3, touch). Real WebKit with VISUAL_WEBKIT=1; the default is Chromium
    // emulation because on WSL WebKit lets XHRs bypass `page.route`, so mocks never apply.
    use: {
      ...devices["iPhone 15"],
      ...VISUAL_LOCALE,
      ...(process.env.VISUAL_WEBKIT === "1"
        ? {}
        : {
            defaultBrowserType: "chromium" as const,
            userAgent: devices["Desktop Chrome"].userAgent,
          }),
    },
  },
  {
    name: "visual-tablet",
    testMatch: "**/e2e/visual/**/*.spec.ts",
    use: { ...devices["Desktop Chrome"], ...VISUAL_LOCALE, viewport: { width: 820, height: 1180 } },
  },
  {
    name: "visual-desktop",
    testMatch: "**/e2e/visual/**/*.spec.ts",
    use: { ...devices["Desktop Chrome"], ...VISUAL_LOCALE, viewport: { width: 1440, height: 900 } },
  },
];

// Example of the final shape (do not copy literally; merge into the app's config):
export default defineConfig({
  // Keep Playwright's per-test artefacts apart: it wipes `outputDir` on every run, which would
  // delete `test-results/visual/*` screenshots and the report.
  outputDir: "test-results/.playwright",
  projects: [
    // { name: "iphone", testIgnore: VISUAL_GLOB, use: { ...devices["iPhone 15"] } },
    ...VISUAL_PROJECTS,
  ],
});
