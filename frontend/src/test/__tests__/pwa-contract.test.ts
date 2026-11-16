// Fleet PWA contract (`pwa-mobile.md`): audit 2026-11-13 template-gap-05 — the template shipped
// the TanStack sample manifest, no sw.js and a viewport without viewport-fit=cover.
// @vitest-environment node
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(__dirname, "../../..");
const read = (path: string) => readFileSync(resolve(root, path), "utf8");

describe("PWA contract", () => {
  const manifest = JSON.parse(read("public/manifest.json"));
  const html = read("index.html");

  it("manifest is the app's own, installable and minimal-ui", () => {
    expect(manifest.name).not.toMatch(/tanstack/i);
    expect(manifest.short_name).not.toMatch(/tanstack/i);
    expect(manifest.display).toBe("minimal-ui");
    expect(manifest.scope).toBe("/");
    expect(manifest.start_url).toBe("/");
  });

  it("has an any and a separate maskable icon, all present in public/", () => {
    const purposes = manifest.icons.map((icon: { purpose?: string }) => icon.purpose);
    expect(purposes).toContain("any");
    expect(purposes).toContain("maskable");
    for (const icon of manifest.icons as { src: string }[]) {
      expect(existsSync(resolve(root, "public", icon.src))).toBe(true);
    }
  });

  it("index.html links the manifest and covers the notch / iOS standalone", () => {
    expect(html).toContain("viewport-fit=cover");
    expect(html).toContain("interactive-widget=resizes-content");
    expect(html).toContain('rel="manifest"');
    expect(html).toContain('rel="apple-touch-icon"');
    expect(html).toContain('name="apple-mobile-web-app-capable"');
    expect(html).toContain('name="apple-mobile-web-app-title"');
  });

  it("sw.js exists and never caches (no fetch handler)", () => {
    const sw = read("public/sw.js");
    expect(sw).toContain('addEventListener("install"');
    expect(sw).not.toMatch(/addEventListener\(\s*["']fetch["']/);
    expect(sw).not.toMatch(/caches\./);
  });
});
