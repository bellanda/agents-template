/** Números → texto pt-BR (vírgula decimal, ponto de milhar). Padrão da frota; nunca `toFixed` em tela. */

/** Cache of pt-BR formatters per fraction-digit count (one `Intl.NumberFormat` per precision). */
const DECIMAL_FORMATTERS = new Map<number, Intl.NumberFormat>();

/**
 * Número com `digits` casas fixas e vírgula decimal pt-BR ("0,874"). Substitui `toFixed`, que
 * imprime ponto decimal e destoa do resto da UI (audit 2026-11-15 r2-optimuslar-fe-03).
 */
export function formatDecimal(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  let formatter = DECIMAL_FORMATTERS.get(digits);
  if (!formatter) {
    formatter = new Intl.NumberFormat("pt-BR", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    DECIMAL_FORMATTERS.set(digits, formatter);
  }
  return formatter.format(value);
}

const MILLION = 1_000_000;
const THOUSAND = 1_000;

/** Eixo/legenda compacta: "R$ 1,5M", "R$ 850K", "R$ 900" (pt-BR, uma casa só nos milhões). */
export function formatCurrencyShort(value: number): string {
  if (value >= MILLION) return `R$ ${formatDecimal(value / MILLION, 1)}M`;
  if (value >= THOUSAND) return `R$ ${formatDecimal(value / THOUSAND, 0)}K`;
  return `R$ ${formatDecimal(value, 0)}`;
}
