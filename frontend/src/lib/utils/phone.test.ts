// Telefone canônico da frota — CÓPIA IDÊNTICA em todo app (espelho de `tests/core/test_phones.py`).
import { describe, expect, it } from "vitest";
import {
  canonicalPhone,
  formatPhone,
  localPhoneDigits,
  phoneFieldError,
  PHONE_MOBILE_INCOMPLETE_MESSAGE,
  whatsAppUrl,
} from "./phone";

describe("canonicalPhone", () => {
  it.each([
    // Regressão kailos prod 2026-10-29: o `wa_id` sem o 9 é a MESMA linha da planilha com o 9.
    ["+553591107807", "5535991107807"],
    ["553591107807", "5535991107807"],
    ["(35) 99110-7807", "5535991107807"],
    ["+55 35 99110-7807", "5535991107807"],
    ["035991107807", "5535991107807"],
    ["(35) 9110-7807", "5535991107807"],
    ["(34) 3210-1234", "553432101234"],
    ["55991234567", "5555991234567"],
    ["+1 415 555 2671", "14155552671"],
    ["14155552671", "14155552671"],
    ["5535191107807", null],
    ["+55 10 99110-7807", null],
    ["190", null],
    ["", null],
  ])("%s -> %s", (raw, expected) => {
    expect(canonicalPhone(raw)).toBe(expected);
    if (expected) expect(canonicalPhone(expected)).toBe(expected);
  });
});

describe("display and input helpers", () => {
  it("formats every stored spelling the same way", () => {
    expect(formatPhone("553591107807")).toBe("(35) 99110-7807");
    expect(formatPhone("35991107807")).toBe("(35) 99110-7807");
    expect(formatPhone("553432101234")).toBe("(34) 3210-1234");
    expect(formatPhone("14155552671")).toBe("+14155552671");
    expect(formatPhone("ramal 12")).toBe("ramal 12");
    expect(formatPhone(null)).toBe("");
  });

  it("feeds the mask without rewriting what is being typed", () => {
    expect(localPhoneDigits("5535991107807")).toBe("35991107807");
    expect(localPhoneDigits("553591107807")).toBe("35991107807");
    // 10 dígitos digitados = celular pela metade: nunca ganha o 9 no meio da digitação.
    expect(localPhoneDigits("3599110780")).toBe("3599110780");
    expect(phoneFieldError("3599110780")).toBe(PHONE_MOBILE_INCOMPLETE_MESSAGE);
    expect(phoneFieldError("3432101234")).toBeNull();
    expect(phoneFieldError("35991107807")).toBeNull();
    expect(phoneFieldError("")).toBeNull();
    expect(phoneFieldError("1099110780")).not.toBeNull(); // DDD com zero
    expect(phoneFieldError("553591107807")).toBeNull(); // grafia antiga carregada da API
    expect(whatsAppUrl("(35) 99110-7807")).toBe("https://wa.me/5535991107807");
  });
});
