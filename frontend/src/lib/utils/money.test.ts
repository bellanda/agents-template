// @vitest-environment node
import { describe, expect, it } from "vitest";

import { formatCurrencyShort, formatDecimal } from "./money";

describe("formatDecimal / formatCurrencyShort (audit 2026-11-15 r2-optimuslar-fe-03)", () => {
  it("uses the pt-BR decimal comma, never toFixed's dot", () => {
    expect(formatDecimal(0.8744, 3)).toBe("0,874");
    expect(formatDecimal(12.5, 1)).toBe("12,5");
    expect(formatDecimal(null, 2)).toBe("—");
  });

  it.each([
    { value: 1_500_000, text: "R$ 1,5M" },
    { value: 850_000, text: "R$ 850K" },
    { value: 900, text: "R$ 900" },
  ])("short currency $value -> $text", ({ value, text }) => {
    expect(formatCurrencyShort(value)).toBe(text);
  });
});
