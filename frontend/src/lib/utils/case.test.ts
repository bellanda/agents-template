import {
  camelToSnake,
  objectKeysToCamelCase,
  objectKeysToSnakeCase,
  snakeToCamel,
} from "@/lib/utils/case";
import { describe, expect, it } from "vitest";

describe("camelToSnake / snakeToCamel", () => {
  it("converte strings nos dois sentidos", () => {
    expect(camelToSnake("organizationId")).toBe("organization_id");
    expect(snakeToCamel("organization_id")).toBe("organizationId");
  });

  it("round-trip preserva o valor", () => {
    expect(snakeToCamel(camelToSnake("onboardingCompletedAt"))).toBe("onboardingCompletedAt");
  });

  it("string sem maiúscula/underscore fica intacta", () => {
    expect(camelToSnake("nome")).toBe("nome");
    expect(snakeToCamel("nome")).toBe("nome");
  });
});

describe("objectKeysToCamelCase", () => {
  it("converte chaves profundamente, incluindo arrays", () => {
    const input = {
      user_id: 1,
      org_data: { display_name: "Loja", phone_numbers: [{ country_code: "55" }] },
    };
    expect(objectKeysToCamelCase(input)).toEqual({
      userId: 1,
      orgData: { displayName: "Loja", phoneNumbers: [{ countryCode: "55" }] },
    });
  });

  it("preserva primitivos e null", () => {
    expect(objectKeysToCamelCase(null)).toBeNull();
    expect(objectKeysToCamelCase("texto")).toBe("texto");
    expect(objectKeysToCamelCase(42)).toBe(42);
  });
});

describe("objectKeysToSnakeCase", () => {
  it("converte chaves profundamente", () => {
    const input = { userId: 1, orgData: { displayName: "Loja" } };
    expect(objectKeysToSnakeCase(input)).toEqual({
      user_id: 1,
      org_data: { display_name: "Loja" },
    });
  });

  it("round-trip de objeto preserva a estrutura", () => {
    const original = { vehiclePhotos: [{ fileId: "abc", position: 0 }] };
    expect(objectKeysToCamelCase(objectKeysToSnakeCase(original))).toEqual(original);
  });
});
