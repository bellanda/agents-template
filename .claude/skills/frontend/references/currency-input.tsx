import { Input } from "@/components/ui/input";
import { parseDecimalBR, toDecimalInput } from "@/lib/utils/currency";
import * as React from "react";

interface CurrencyInputProps extends Omit<
  React.ComponentProps<typeof Input>,
  "onChange" | "value" | "type" | "inputMode"
> {
  /** Texto digitado, como o usuário vê ("1.500,00"). Converta no submit com `parseMoney(value)`. */
  value: string;
  onChange: (value: string) => void;
  /** Casas decimais aceitas e usadas ao normalizar no blur: 2 = dinheiro/percentual, 3 = quantidade. */
  decimals?: number;
  allowNegative?: boolean;
}

/**
 * Campo de dinheiro/decimal pt-BR (audit 2026-11-13 promoservice-fe-finance-stock-01).
 *
 * O estado do pai continua sendo a STRING digitada; o submit usa `parseMoney` /
 * `parseDecimalBR` (`lib/utils/currency.ts`) e bloqueia o envio quando devolve `null`.
 * O componente só: teclado numérico no celular (`inputMode="decimal"`), descarta letras ao
 * digitar, marca `aria-invalid` quando o texto é ambíguo ("1,500.00") e, no blur, normaliza
 * um valor válido para vírgula sem milhar ("1.500" → "1500,00") para a pessoa CONFERIR o que
 * será enviado antes de salvar.
 *
 *   <CurrencyInput value={amount} onChange={setAmount} placeholder="0,00" />
 */
export function CurrencyInput({
  value,
  onChange,
  onBlur,
  decimals = 2,
  allowNegative = false,
  ...props
}: CurrencyInputProps) {
  const [touched, setTouched] = React.useState(false);
  const invalid =
    touched &&
    value.trim() !== "" &&
    parseDecimalBR(value, { maxDecimals: decimals, allowNegative }) === null;

  return (
    <Input
      {...props}
      inputMode="decimal"
      autoComplete="off"
      value={value}
      aria-invalid={invalid || props["aria-invalid"] ? true : undefined}
      onChange={(event) => {
        const allowed = allowNegative ? /[^\d.,-]/g : /[^\d.,]/g;
        onChange(event.target.value.replace(allowed, ""));
      }}
      onBlur={(event) => {
        setTouched(true);
        const parsed = parseDecimalBR(value, { maxDecimals: decimals, allowNegative });
        if (parsed !== null) {
          const normalized = toDecimalInput(parsed, decimals);
          if (normalized !== value) onChange(normalized);
        }
        onBlur?.(event);
      }}
    />
  );
}
