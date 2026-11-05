/**
 * App-agnostic automated visual checks (visual QA harness, 2026-11-05).
 * Everything here runs inside the page via `page.evaluate`; nothing knows about Kailos routes.
 * Findings are `hard` (fail the test) or `warn` (report only). See README.md.
 */
import type { ConsoleMessage, Page } from "@playwright/test";

export type Severity = "hard" | "warn";

export interface Finding {
  routeId: string;
  viewport: string;
  severity: Severity;
  kind: string;
  selector: string;
  detail: string;
}

type RawFinding = Omit<Finding, "routeId" | "viewport">;

const MIN_TOUCH_TARGET_PX = 36;
const MAX_FINDINGS_PER_KIND = 12;
const OVERLAP_TOLERANCE_PX = 2;

/** Runs in the browser. Kept as ONE self-contained function (no closures over node scope). */
function collectInPage(args: { isMobile: boolean; minTouch: number; overlapTol: number }) {
  const out: RawFinding[] = [];
  // Dev-only overlays (TanStack Query/Router devtools) are not the product UI.
  const DEV_TOOLS =
    ".tsqd-parent-container, [class*='tsqd'], [class*='TanStackRouterDevtools'], [class^='go']";
  const vw = document.documentElement.clientWidth;
  const vh = window.innerHeight;

  const selectorOf = (el: Element): string => {
    const id = el.getAttribute("data-testid") || el.id;
    const cls = String((el as HTMLElement).className || "")
      .split(/\s+/)
      .filter((c) => c && !c.includes(":") && !c.startsWith("[") && c.length < 24)
      .slice(0, 3)
      .join(".");
    const text = (el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 32);
    return `${el.tagName.toLowerCase()}${id ? `#${id}` : ""}${cls ? `.${cls}` : ""}${text ? ` "${text}"` : ""}`;
  };
  const isVisible = (el: Element): boolean => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const s = getComputedStyle(el);
    return s.visibility !== "hidden" && s.display !== "none" && Number(s.opacity) > 0.01;
  };
  /** True when an ancestor scrolls/clips horizontally on purpose (carousel, table wrapper, sr-only). */
  const insideClipper = (el: Element): boolean => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (/(auto|scroll|hidden|clip)/.test(s.overflowX)) {
        const pr = p.getBoundingClientRect();
        if (pr.right <= vw + 1 && pr.left >= -1) return true;
      }
    }
    return false;
  };

  // 1. Document horizontal overflow (hard).
  const docEl = document.documentElement;
  if (docEl.scrollWidth > docEl.clientWidth + 1) {
    out.push({
      severity: "hard",
      kind: "document-overflow",
      selector: "html",
      detail: `scrollWidth=${docEl.scrollWidth} clientWidth=${docEl.clientWidth}`,
    });
  }
  const main = document.querySelector("main");
  if (main && main.scrollWidth > main.clientWidth + 1) {
    const ov = getComputedStyle(main).overflowX;
    if (ov === "visible" || ov === "hidden") {
      out.push({
        severity: "hard",
        kind: "main-overflow",
        selector: selectorOf(main),
        detail: `main scrollWidth=${main.scrollWidth} clientWidth=${main.clientWidth}`,
      });
    }
  }

  // 2. Visible element wider than / past the viewport (hard). Leaf-most culprits only.
  const all = Array.from(document.body.querySelectorAll<HTMLElement>("*"));
  const offscreen = all.filter((el) => {
    if (!isVisible(el) || insideClipper(el)) return false;
    if (el.closest("[data-sonner-toaster],[aria-hidden='true'],.sr-only")) return false;
    const r = el.getBoundingClientRect();
    return r.right > vw + 1 || r.left < -1;
  });
  for (const el of offscreen
    .filter((el) => !Array.from(el.children).some((c) => offscreen.includes(c as HTMLElement)))
    .slice(0, 12)) {
    const r = el.getBoundingClientRect();
    out.push({
      severity: "hard",
      kind: "past-viewport",
      selector: selectorOf(el),
      detail: `left=${Math.round(r.left)} right=${Math.round(r.right)} viewport=${vw}`,
    });
  }

  // 3. Touch targets (warn, mobile only).
  if (args.isMobile) {
    const targets = Array.from(
      document.querySelectorAll<HTMLElement>(
        "button, a[href], [role=button], [role=tab], [role=menuitem], input:not([type=hidden]), select, textarea, [role=checkbox], [role=switch]"
      )
    );
    for (const el of targets) {
      if (!isVisible(el) || el.closest("[aria-hidden='true']") || el.closest(DEV_TOOLS)) continue;
      const r = el.getBoundingClientRect();
      if (r.right < 0 || r.left > vw) continue;
      // Inline text links inside paragraphs are exempt (WCAG inline exception).
      if (el.tagName === "A" && el.closest("p, li") && r.height < args.minTouch) continue;
      if (r.width < args.minTouch || r.height < args.minTouch) {
        // A pseudo-element can extend the hit area past the box (shadcn Checkbox, FieldHint):
        // probe points around the centre and accept when they still land on this control.
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        const half = args.minTouch / 2 - 1;
        const hits = (x: number, y: number) => {
          const hit = document.elementFromPoint(x, y);
          return !!hit && (hit === el || el.contains(hit));
        };
        const extended =
          hits(cx - half, cy) && hits(cx + half, cy) && hits(cx, cy - half) && hits(cx, cy + half);
        if (extended) continue;
        out.push({
          severity: "warn",
          kind: "small-touch-target",
          selector: selectorOf(el),
          detail: `${Math.round(r.width)}x${Math.round(r.height)} (min-h ${getComputedStyle(el).minHeight}, pointer-coarse ${matchMedia("(pointer: coarse)").matches})`,
        });
      }
    }
  }

  // 4. Open dialog: footer / primary button inside the viewport (hard) and dialog not taller than viewport.
  for (const dialog of Array.from(
    document.querySelectorAll<HTMLElement>("[role=dialog], [role=alertdialog]")
  )) {
    if (!isVisible(dialog)) continue;
    const dr = dialog.getBoundingClientRect();
    if (dr.bottom > vh + 1 || dr.top < -1 || dr.right > vw + 1 || dr.left < -1) {
      out.push({
        severity: "hard",
        kind: "dialog-off-screen",
        selector: selectorOf(dialog),
        detail: `rect top=${Math.round(dr.top)} bottom=${Math.round(dr.bottom)} left=${Math.round(dr.left)} right=${Math.round(dr.right)} viewport=${vw}x${vh}`,
      });
    }
    const footerButtons = Array.from(
      dialog.querySelectorAll<HTMLElement>("[data-slot=dialog-footer] button, footer button")
    ).filter(isVisible);
    for (const btn of footerButtons) {
      const r = btn.getBoundingClientRect();
      if (r.bottom > vh + 1 || r.top < 0 || r.right > vw + 1 || r.left < -1) {
        out.push({
          severity: "hard",
          kind: "dialog-footer-off-screen",
          selector: selectorOf(btn),
          detail: `button top=${Math.round(r.top)} bottom=${Math.round(r.bottom)} viewport=${vw}x${vh}`,
        });
      }
    }
  }

  // 5. Overlapping siblings in header / toolbar rows (warn): direct children of a flex row
  // whose boxes intersect (clipping is fine; overlap is not).
  const rows = Array.from(
    document.querySelectorAll<HTMLElement>(
      "header, [role=toolbar], [data-slot=toolbar], main > div > div"
    )
  ).filter((row) => isVisible(row) && getComputedStyle(row).display.includes("flex"));
  for (const row of rows) {
    const kids = Array.from(row.children).filter(
      (k) => isVisible(k) && getComputedStyle(k).position !== "absolute"
    );
    for (let i = 0; i < kids.length; i++) {
      for (let j = i + 1; j < kids.length; j++) {
        const a = kids[i].getBoundingClientRect();
        const b = kids[j].getBoundingClientRect();
        const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (w > args.overlapTol && h > args.overlapTol) {
          out.push({
            severity: "warn",
            kind: "overlapping-siblings",
            selector: `${selectorOf(kids[i])}  x  ${selectorOf(kids[j])}`,
            detail: `overlap ${Math.round(w)}x${Math.round(h)}px in ${selectorOf(row)}`,
          });
        }
      }
    }
  }

  // 6. Text clipped WITHOUT an ellipsis (warn): overflow hidden + scrollWidth > clientWidth and
  // no text-overflow:ellipsis / line-clamp => letters cut mid-glyph.
  for (const el of all) {
    if (!isVisible(el) || el.children.length > 0 || !el.textContent?.trim()) continue;
    if (el.classList.contains("sr-only") || el.closest(DEV_TOOLS)) continue;
    const s = getComputedStyle(el);
    if (!/(hidden|clip)/.test(s.overflowX) || el.scrollWidth <= el.clientWidth + 1) continue;
    if (s.textOverflow === "ellipsis" || s.webkitLineClamp !== "none") continue;
    out.push({
      severity: "warn",
      kind: "text-clipped-no-ellipsis",
      selector: selectorOf(el),
      detail: `scrollWidth=${el.scrollWidth} clientWidth=${el.clientWidth}`,
    });
  }

  // 7. Wrapped tab lists (warn): a tablist taller than 1.5 rows.
  for (const list of Array.from(document.querySelectorAll<HTMLElement>("[role=tablist]"))) {
    if (!isVisible(list)) continue;
    const tabs = Array.from(list.querySelectorAll<HTMLElement>("[role=tab]")).filter(isVisible);
    const tallest = Math.max(0, ...tabs.map((t) => t.getBoundingClientRect().height));
    if (tallest > 0 && list.getBoundingClientRect().height > tallest * 1.5) {
      out.push({
        severity: "warn",
        kind: "tablist-wraps",
        selector: selectorOf(list),
        detail: `list height ${Math.round(list.getBoundingClientRect().height)} vs tab ${Math.round(tallest)}`,
      });
    }
  }
  return out;
}

export async function runChecks(
  page: Page,
  routeId: string,
  viewport: string,
  isMobile: boolean
): Promise<Finding[]> {
  const raw = (await page.evaluate(collectInPage, {
    isMobile,
    minTouch: MIN_TOUCH_TARGET_PX,
    overlapTol: OVERLAP_TOLERANCE_PX,
  })) as RawFinding[];
  const perKind = new Map<string, number>();
  return raw
    .filter((finding) => {
      const count = (perKind.get(finding.kind) ?? 0) + 1;
      perKind.set(finding.kind, count);
      return count <= MAX_FINDINGS_PER_KIND;
    })
    .map((finding) => ({ ...finding, routeId, viewport }));
}

/** Collects console errors + uncaught page errors for the whole route visit. */
export function watchRuntimeErrors(page: Page, routeId: string, viewport: string) {
  const findings: Finding[] = [];
  // Noise that is mock/dev-server artefact, not an app bug.
  const IGNORED = [
    /Failed to load resource/i,
    /favicon/i,
    /net::ERR/i,
    /\[vite\]/i,
    /ResizeObserver loop/i,
  ];
  page.on("console", (msg: ConsoleMessage) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    if (IGNORED.some((re) => re.test(text))) return;
    findings.push({
      routeId,
      viewport,
      severity: "hard",
      kind: "console-error",
      selector: msg.location().url.split("/").slice(-2).join("/"),
      detail: text.slice(0, 300),
    });
  });
  page.on("pageerror", (error) => {
    findings.push({
      routeId,
      viewport,
      severity: "hard",
      kind: "page-error",
      selector: "window",
      detail: String(error.message).slice(0, 300),
    });
  });
  return findings;
}
