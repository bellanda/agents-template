/**
 * Parse de dinheiro/decimal digitado em pt-BR (audit 2026-11-13 promoservice-fe-finance-stock-01).
 *
 * Por que existe: `texto.replace(",", ".")` troca só a primeira vírgula e deixa o ponto de milhar:
 * "1.500" virava 1,5 (baixa de R$ 1.500 registrada como R$ 1,50) e "1.500,00" era recusado.
 * O backend usa Decimal e aceita "1.500" como 1.5, então nada barrava. TODO campo de dinheiro,
 * quantidade ou percentual digitado passa por aqui; `replace(",", ".")` em call site é proibido.
 *
 * Regras (ponto = milhar, vírgula = decimal, como se digita no Brasil):
 * - "1.500" = 1500 · "1.500,00" = 1500 · "1500,5" = 1500.5 · "12,30" = 12.3 · "R$ 1.234,56" ok;
 * - "12.5" = 12.5 (um ponto com 1-2 casas só pode ser decimal);
 * - REJEITA o ambíguo/malformado → `null`: "1,500.00" (formato en-US), "1.5.0", "1,2,3",
 *   "1234.567" (3 casas depois de um ponto, sem grupo de milhar válido), "0.500", "abc", "".
 * O retorno é a string decimal canônica ("1500.5") — vai direto para o backend (Decimal) sem
 * passar por float; `parseMoneyNumber` existe para quem precisa de `number` (cálculo local).
 */

const THOUSANDS_GROUPED = /^[1-9]\d{0,2}(\.\d{3})+$/;
const MONEY_DECIMALS = 2;
const DEFAULT_MAX_DECIMALS = 6;

interface ParseDecimalOptions {
  /** Mais casas que isso é recusado (nunca arredondado em silêncio). */
  maxDecimals?: number;
  allowNegative?: boolean;
}

export function parseDecimalBR(
  input: string | null | undefined,
  { maxDecimals = DEFAULT_MAX_DECIMALS, allowNegative = false }: ParseDecimalOptions = {}
): string | null {
  if (typeof input !== "string") return null;
  let text = input.replace(/R\$|\s/g, "");
  if (text === "") return null;

  let sign = "";
  if (text.startsWith("-")) {
    if (!allowNegative) return null;
    sign = "-";
    text = text.slice(1);
  }
  if (!/^[\d.,]+$/.test(text)) return null;

  let intPart: string;
  let fracPart = "";
  const commaParts = text.split(",");
  if (commaParts.length > 2) return null;

  if (commaParts.length === 2) {
    const [whole, frac] = commaParts;
    // Pontos antes da vírgula têm de ser grupos de milhar válidos; "1,500.00" cai aqui e é recusado.
    if (whole.includes(".") && !THOUSANDS_GROUPED.test(whole)) return null;
    if (frac === "" || frac.includes(".")) return null;
    intPart = whole.replaceAll(".", "");
    fracPart = frac;
  } else if (text.includes(".")) {
    if (THOUSANDS_GROUPED.test(text)) {
      intPart = text.replaceAll(".", "");
    } else {
      const dotParts = text.split(".");
      if (dotParts.length !== 2) return null;
      [intPart, fracPart] = dotParts;
      // 3 casas depois de um ponto é o desenho de milhar ("1234.567", "0.500"): ambíguo, recusa.
      if (fracPart === "" || fracPart.length === 3) return null;
    }
  } else {
    intPart = text;
  }

  if (intPart === "" && fracPart === "") return null;
  if (fracPart.length > maxDecimals) return null;

  const whole = intPart.replace(/^0+(?=\d)/, "") || "0";
  const frac = fracPart.replace(/0+$/, "");
  return `${sign}${whole}${frac ? `.${frac}` : ""}`;
}

/** Dinheiro em reais (até 2 casas). `null` = vazio ou ambíguo — a tela mostra erro, não envia. */
export function parseMoney(
  input: string | null | undefined,
  options: Omit<ParseDecimalOptions, "maxDecimals"> = {}
): string | null {
  return parseDecimalBR(input, { ...options, maxDecimals: MONEY_DECIMALS });
}

/** Igual a `parseMoney`, devolvendo `number` (só para cálculo/validação local; ao backend vai a string). */
export function parseMoneyNumber(
  input: string | null | undefined,
  options: Omit<ParseDecimalOptions, "maxDecimals"> = {}
): number | null {
  const parsed = parseMoney(input, options);
  return parsed === null ? null : Number(parsed);
}

/** Valor do backend ("1500.50" ou number) → texto para pré-preencher o campo ("1500,50"), sem milhar. */
export function toDecimalInput(
  value: string | number | null | undefined,
  decimals = MONEY_DECIMALS
): string {
  if (value === null || value === undefined || value === "") return "";
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return "";
  return amount.toFixed(decimals).replace(".", ",");
}
