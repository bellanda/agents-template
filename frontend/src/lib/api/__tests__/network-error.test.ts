import { describe, expect, it } from "vitest";
import { httpStatusFallbackMessage } from "../network-error";

// Regression: a 413 from nginx (HTML body) used to surface as an English generic message.
describe("httpStatusFallbackMessage", () => {
  it("explains 413 and gateway failures in pt-BR, others generically", () => {
    expect(httpStatusFallbackMessage(413)).toContain("grande demais");
    for (const status of [502, 503, 504]) {
      expect(httpStatusFallbackMessage(status)).toContain("indisponível");
    }
    expect(httpStatusFallbackMessage(418)).toContain("HTTP 418");
    expect(httpStatusFallbackMessage(undefined)).toBe("Erro inesperado do servidor.");
  });
});
