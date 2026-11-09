// @vitest-environment jsdom (the template does not set `test.environment` in vite.config)
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import {
  bootFontSize,
  DEFAULT_FONT_SIZE,
  FONT_SIZES,
  getActiveFontSize,
  syncFontSizeFromAccount,
} from "../font-size";

const CACHE_KEY = "app:font-size:v1";
const SRC = resolve(__dirname, "../../..");
const FONT_SIZE_CSS = readFileSync(resolve(SRC, "styles/themes/font-size.css"), "utf8");
const INDEX_CSS = readFileSync(resolve(SRC, "styles.css"), "utf8");
const BACKEND_SCHEMA = readFileSync(
  resolve(SRC, "../../backend/src/api/schemas/accounts/accounts.py"),
  "utf8"
);
// Print layouts are sized for paper on purpose and the print media rule resets the scale anyway.
const IS_PRINT_PATH = /(^|\/)print(\/|$)/;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "__tests__" ? [] : sourceFiles(path);
    return /\.tsx?$/.test(path) && !/\.test\.tsx?$/.test(path) ? [path] : [];
  });
}

describe("font size", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-font-size");
  });

  it("has a CSS scale for every non-default id and scales the root font", () => {
    for (const { id } of FONT_SIZES) {
      if (id === DEFAULT_FONT_SIZE) continue;
      expect(FONT_SIZE_CSS, id).toContain(`[data-font-size="${id}"]`);
    }
    expect(INDEX_CSS).toContain("./styles/themes/font-size.css");
    expect(INDEX_CSS).toContain("var(--app-font-scale, 1)");
  });

  it("matches the backend FontSizeId Literal", () => {
    const literal = BACKEND_SCHEMA.match(/FontSizeId = Literal\[([\s\S]*?)\]/)?.[1] ?? "";
    const backendIds = [...literal.matchAll(/"([a-z-]+)"/g)].map((match) => match[1]).sort();
    expect(backendIds).toEqual(FONT_SIZES.map((size) => size.id).sort());
  });

  it("paints the cached size on boot and falls back to the default", () => {
    bootFontSize();
    expect(getActiveFontSize()).toBe(DEFAULT_FONT_SIZE);
    localStorage.setItem(CACHE_KEY, "muito-grande");
    bootFontSize();
    expect(document.documentElement.getAttribute("data-font-size")).toBe("muito-grande");
    localStorage.setItem(CACHE_KEY, "gigante");
    bootFontSize();
    expect(getActiveFontSize()).toBe(DEFAULT_FONT_SIZE);
  });

  it("follows the account when its value changes and ignores unknown ids", () => {
    bootFontSize();
    syncFontSizeFromAccount("grande");
    expect(getActiveFontSize()).toBe("grande");
    expect(localStorage.getItem(CACHE_KEY)).toBe("grande");
    syncFontSizeFromAccount("gigante");
    expect(getActiveFontSize()).toBe("grande");
  });

  // Regression guard: a fixed `text-[11px]` ignores the preference, and it is the smallest text
  // on screen, exactly what people complained about (2026-11-09).
  it("keeps text sizes in rem so they follow the preference", () => {
    const offenders = sourceFiles(SRC).flatMap((file) => {
      const path = relative(SRC, file);
      if (IS_PRINT_PATH.test(path)) return [];
      return [...readFileSync(file, "utf8").matchAll(/text-\[[1-9][0-9.]*px\]/g)].map(
        (match) => `${path}: ${match[0]}`
      );
    });
    expect(offenders).toEqual([]);
  });
});
