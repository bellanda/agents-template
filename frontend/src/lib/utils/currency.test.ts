import { describe, expect, it } from "vitest";
import { parseDecimalBR, parseMoney, parseMoneyNumber, toDecimalInput } from "./currency";

describe("parseMoney", () => {
  it.each([
    ["1.500", "1500"],
    ["1.500,00", "1500"],
    ["1500,5", "1500.5"],
    ["12,30", "12.3"],
    ["12.5", "12.5"],
    ["0,99", "0.99"],
    [",5", "0.5"],
    ["R$ 1.234,56", "1234.56"],
    ["1.234.567,89", "1234567.89"],
    ["007", "7"],
    ["0", "0"],
  ])("%s -> %s", (input, expected) => {
    expect(parseMoney(input)).toBe(expected);
  });

  it.each([
    "",
    "   ",
    "abc",
    "1,500.00", // en-US: ambiguous with pt-BR
    "1.5.0",
    "1,2,3",
    "1234.567",
    "0.500",
    "12,",
    "1,234",
    "10,123", // 3 decimals: not money
    "-5",
    "1.50,5",
  ])("rejects %j", (input) => {
    // "1,234" = 1.234 has 3 decimals, which is not money; "10,123" likewise.
    expect(parseMoney(input)).toBeNull();
  });

  it("is null-safe", () => {
    expect(parseMoney(null)).toBeNull();
    expect(parseMoney(undefined)).toBeNull();
  });

  it("parseMoneyNumber returns a number", () => {
    expect(parseMoneyNumber("1.500,50")).toBe(1500.5);
    expect(parseMoneyNumber("x")).toBeNull();
  });
});

describe("parseDecimalBR", () => {
  it("accepts more decimals for quantities", () => {
    expect(parseDecimalBR("2,125", { maxDecimals: 3 })).toBe("2.125");
    expect(parseDecimalBR("2,1255", { maxDecimals: 3 })).toBeNull();
  });

  it("only accepts a negative sign when asked", () => {
    expect(parseDecimalBR("-1.500,5")).toBeNull();
    expect(parseDecimalBR("-1.500,5", { allowNegative: true })).toBe("-1500.5");
  });
});

describe("toDecimalInput", () => {
  it("renders backend decimals with a comma and no thousands separator", () => {
    expect(toDecimalInput("1500.5")).toBe("1500,50");
    expect(toDecimalInput(12)).toBe("12,00");
    expect(toDecimalInput("2.5", 3)).toBe("2,500");
    expect(toDecimalInput(null)).toBe("");
    expect(toDecimalInput("abc")).toBe("");
  });
});
