/**
 * `?page=` da URL de uma lista paginada. Página 1 não aparece na URL (link limpo),
 * e valor que não é inteiro positivo — link velho, digitado à mão — vira página 1.
 */
export function parsePageSearch(raw: unknown): number | undefined {
  const value = typeof raw === "string" ? Number(raw) : raw;
  if (typeof value !== "number" || !Number.isInteger(value) || value < 2) return undefined;
  return value;
}

/** O que vai para a URL ao trocar de página — página 1 some da URL. */
export function pageSearchValue(page: number): number | undefined {
  return page > 1 ? page : undefined;
}
