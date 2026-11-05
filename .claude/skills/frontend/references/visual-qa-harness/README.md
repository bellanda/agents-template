# Visual QA harness

Agent-run check: open every registered screen at 3 widths, screenshot it, run automated checks,
then LOOK at the PNGs and fix until clean. Added 2026-11-05 (fleet standard; portable).

## When to run

After building/redesigning a big section (new tab, dashboard, list, dialog, settings section),
BEFORE delivering. Not part of `check.sh`/`--e2e` (slow, opt-in).

```bash
cd frontend && E2E_PORT=5191 bun run qa:visual     # pick a free port
```

Filter to the routes you touched: `bun run qa:visual -- --grep vehicle-sale` (any Playwright arg
works; a filtered run keeps the other routes' previous findings in the report).

Projects: `visual-mobile` (iPhone 15 emulation 390x844 (Chromium; `VISUAL_WEBKIT=1` for real WebKit)), `visual-tablet` (820x1180), `visual-desktop`
(1440x900, sidebar open). One run ~ routes x 3 (see runtime in the delivery note).

## Output (`frontend/test-results/visual/`, gitignored)

- `<route-id>/<viewport>.png` - full page. Read them with the Read tool and look for what no
  check catches: cramped toolbars, awkward wrapping, inconsistent spacing, dialogs too tall.
- `<viewport>-scroll-N.png` - when a dialog/settings hub scrolls inside itself, the harness scrolls its
  largest scrollable region and shoots each next screen (max 4). LOOK at these too: the first
  screen alone hides everything below the fold.
- `report.md` / `report.json` - findings `{ routeId, viewport, severity, kind, selector, detail }`.
  - **hard** (fails the test): `document-overflow`, `main-overflow`, `past-viewport`,
    `dialog-off-screen`, `dialog-footer-off-screen`, `console-error`, `page-error`.
  - **warn** (report only): `small-touch-target` (<36px, mobile, measured with `pointer: coarse` emulated, like a real phone; it is applied right before the checks because a full-page screenshot resets it), `overlapping-siblings`
    (header/toolbar row), `text-clipped-no-ellipsis`, `tablist-wraps`.

## Gotchas

- **Locale:** the visual projects run in pt-BR and São Paulo time (`VISUAL_LOCALE` in
  `playwright.config.ts`). The `locale` option alone does NOT reach native `<input type="date|time">`:
  headless Chromium on Linux reads the `LANG` env of the browser process, so `launchOptions.env`
  sets `LANG=pt_BR.UTF-8` (without it: "08:00 AM", "mm/dd/yyyy").
- **Dialog states** are shot at viewport size (a full-page shot would show the page behind the
  overlay leaking below it); the dialog's own scroll goes to `<viewport>-scroll-N.png`.
- **Mock data mirrors the API:** phones canonical without "+" ("5511987654321"), money as numbers,
  dates ISO with Z. A mock in another shape can hide a real bug or fake one. Also read the PNG
  for raw values (canonical phone, ISO date, `null`): the chat header printed the raw phone and
  only the screenshot caught it (2026-11-05).
- **WebKit on WSL** ignores `page.route` for XHRs (pre-existing); mobile is Chromium emulation by
  default, `VISUAL_WEBKIT=1` opts into real WebKit.
- A 17px checkbox inside a 36px+ clickable card/label is reported as `small-touch-target`: that is
  a false positive (the hit area is the card).

## Add a route

Edit `routes.ts`: `{ id, path, data?: "worst" | "empty", setup?(page) }`. `setup` opens the state
to check (dialog, tab, menu). Mock data lives in `fixtures.ts` (snake_case bodies, worst case:
long names, R$ 1.234.567,89, 0 and many items); handlers match on pathname and fall through to
`../fixtures/session.ts` (`installApi`) + `../fixtures/layout-data.ts` (`LAYOUT_QUEUES`).
Endpoint not mocked = empty `PagedResponse`, so the screen mounts empty.

## Fix loop

1. Run, read `report.md`, open the PNGs (all 3 widths of each route you touched).
2. Fix by CSS (container queries per frontend rules, never `useIsMobile`).
3. Re-run until no hard findings and the warnings are explained. Screenshots are the truth: a
   clean report with an ugly PNG is not done.

## LIVE mode (optional, LOCAL stack only - never prod)

`E2E_LIVE=1 E2E_LIVE_URL=http://localhost:<port> E2E_LIVE_EMAIL=... E2E_LIVE_PASSWORD=...
E2E_LIVE_ORG_ID=<uuid> bun run qa:visual` - same registry, no mocks, no dev server. The login
helper in `visual-qa.spec.ts` assumes the labelled email/password form of `/auth/login`.

## Porting to another app

Portable as-is: `checks.ts`, `visual-qa.spec.ts`, `build-report.ts`, the Playwright projects and
the `qa:visual` script. App-specific: `routes.ts`, `fixtures.ts`, and `APP` in `../fixtures/session.ts`.
