/**
 * Visual QA: every registry route x viewport project. Saves a full-page screenshot, runs the
 * automated checks, appends findings to a per-test JSON part (merged by `build-report.ts`).
 * Hard findings fail the test; warnings only reach the report. See README.md.
 */
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { APP } from "../fixtures/session";
import { runChecks, watchRuntimeErrors, type Finding } from "./checks";
import { installVisualMocks } from "./fixtures";
import { ORG_ID, ROUTES } from "./routes";

const OUT_DIR = "test-results/visual";
const SHELL_TIMEOUT_MS = 30_000;
const NETWORK_IDLE_CAP_MS = 8_000;
const SETTLE_MS = 800;
const MAX_SHOT_VIEWPORTS = 2;
const LIVE = process.env.E2E_LIVE === "1";
const LIVE_ORG_ID = process.env.E2E_LIVE_ORG_ID ?? ORG_ID;

/**
 * Chromium's phone emulation (hasTouch) does NOT flip `(pointer: coarse)`, so the app's
 * `pointer-coarse:` touch-target rules never apply and every control would be measured at its
 * desktop size. Real WebKit/iOS already reports coarse, so this is a no-op there.
 */
async function emulateCoarsePointer(page: Page) {
  if (page.context().browser()?.browserType().name() !== "chromium") return;
  const session = await page.context().newCDPSession(page);
  await session.send("Emulation.setEmulatedMedia", {
    features: [
      { name: "pointer", value: "coarse" },
      { name: "any-pointer", value: "coarse" },
      { name: "hover", value: "none" },
    ],
  });
}

const MAX_SCROLL_SHOTS = 4;

/**
 * A dialog/settings hub scrolls INSIDE itself, so the main screenshot only shows its first
 * screen (the holiday section of `settings-hours` was never seen at 390). Scroll the largest
 * scrollable region of the open dialog and shoot each next screen as `<viewport>-scroll-N.png`.
 */
async function captureScrolledDialog(page: Page, dir: string, viewport: string) {
  const handle = await page.evaluateHandle(() => {
    const dialog = document.querySelector("[role=dialog]");
    if (!dialog) return null;
    const scrollers = Array.from(dialog.querySelectorAll<HTMLElement>("*")).filter(
      (el) =>
        /(auto|scroll)/.test(getComputedStyle(el).overflowY) &&
        el.scrollHeight > el.clientHeight + 8
    );
    scrollers.sort((a, b) => b.scrollHeight - a.scrollHeight);
    return scrollers[0] ?? null;
  });
  const scroller = handle.asElement();
  if (!scroller) return;
  for (let shot = 1; shot <= MAX_SCROLL_SHOTS; shot++) {
    const atEnd = await scroller.evaluate((el) => {
      el.scrollTop += el.clientHeight * 0.85;
      return el.scrollTop + el.clientHeight >= el.scrollHeight - 2;
    });
    await page.waitForTimeout(150);
    await page.screenshot({ path: `${dir}/${viewport}-scroll-${shot}.png` });
    if (atEnd) return;
  }
}

async function loginLive(page: Page) {
  await page.goto(APP.loginPath);
  await page.getByLabel(/e-?mail/i).fill(process.env.E2E_LIVE_EMAIL ?? "");
  await page.getByLabel(/senha/i).fill(process.env.E2E_LIVE_PASSWORD ?? "");
  await page.getByRole("button", { name: /entrar/i }).click();
}

for (const route of ROUTES) {
  test(`visual ${route.id}`, async ({ page }, testInfo) => {
    const viewport = testInfo.project.name.replace(/^visual-/, "");
    const isMobile = viewport === "mobile";
    const runtimeFindings = watchRuntimeErrors(page, route.id, viewport);

    if (LIVE) await loginLive(page);
    else await installVisualMocks(page, route.data ?? "worst");
    await page.goto(route.path.replace(ORG_ID, LIVE_ORG_ID));

    if (route.waitFor) {
      // Modal states (settings dialog) aria-hide the shell: wait for the modal itself.
      await expect(page.locator(route.waitFor).first()).toBeVisible({ timeout: SHELL_TIMEOUT_MS });
    } else {
      await expect(page.getByRole("button", { name: APP.appShellControl }).first()).toBeVisible({
        timeout: SHELL_TIMEOUT_MS,
      });
      // Some apps render the page h1 inside <main>, not the shell header (optimuslar).
      await expect(page.locator("header h1, main h1").first()).not.toBeEmpty({
        timeout: SHELL_TIMEOUT_MS,
      });
    }
    await page
      .waitForLoadState("networkidle", { timeout: NETWORK_IDLE_CAP_MS })
      .catch(() => undefined);
    await route.setup?.(page);
    // After navigation: Playwright's own emulateMedia calls replace CDP media features.
    if (isMobile) await emulateCoarsePointer(page);
    await page.waitForTimeout(SETTLE_MS);
    // Dev-only floating devtools buttons cover content in the screenshots.
    await page.addStyleTag({
      content: `.tsqd-parent-container, [aria-label*="TanStack" i], [aria-label*="Tanstack query" i], img[alt*="TanStack" i] { display: none !important; }`,
    });
    await page.evaluate(() => {
      for (const el of Array.from(document.querySelectorAll<HTMLElement>("body > *"))) {
        if (
          el.textContent?.includes("TanStack Router") &&
          getComputedStyle(el).position === "fixed"
        )
          el.style.display = "none";
      }
      for (const el of Array.from(document.querySelectorAll<HTMLElement>("body *"))) {
        if (
          getComputedStyle(el).position === "fixed" &&
          /TanStack Router/.test(el.textContent ?? "") &&
          el.textContent!.length < 40
        )
          el.style.display = "none";
      }
    });

    // Measure BEFORE the full-page screenshot: it resizes the viewport via CDP and resets the
    // emulated media features (pointer: coarse), which would hide the touch-target rules.
    const findings: Finding[] = [
      ...(await runChecks(page, route.id, viewport, isMobile)),
      ...runtimeFindings,
    ];

    const dir = `${OUT_DIR}/${route.id}`;
    mkdirSync(dir, { recursive: true });
    // Long lists would be unreadable once downscaled by the image viewer: cap the capture at
    // MAX_SHOT_VIEWPORTS screens tall (the checks still measure the whole DOM).
    const size = page.viewportSize() ?? { width: 390, height: 844 };
    const pageHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    // With a dialog open the page behind it is irrelevant (and a full-page shot shows the list
    // leaking below the overlay): shoot the viewport only; the dialog's own scroll is captured
    // by `captureScrolledDialog`.
    const hasDialog = await page.locator("[role=dialog]").count();
    await page.screenshot(
      hasDialog
        ? { path: `${dir}/${viewport}.png` }
        : {
            path: `${dir}/${viewport}.png`,
            fullPage: true,
            clip: {
              x: 0,
              y: 0,
              width: size.width,
              height: Math.min(pageHeight, size.height * MAX_SHOT_VIEWPORTS),
            },
          }
    );

    await captureScrolledDialog(page, dir, viewport);
    mkdirSync(`${OUT_DIR}/_parts`, { recursive: true });
    writeFileSync(`${OUT_DIR}/_parts/${route.id}__${viewport}.json`, JSON.stringify(findings));

    const hard = findings.filter((finding) => finding.severity === "hard");
    expect(hard, hard.map((f) => `[${f.kind}] ${f.selector} :: ${f.detail}`).join("\n")).toEqual(
      []
    );
  });
}
