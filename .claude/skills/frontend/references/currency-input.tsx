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
  /**
   * Casas decimais aceitas e usadas ao normalizar no blur: 2 = dinheiro/percentual, 3 = quantidade.
   * `0` = modo inteiro (km, dias, minutos, unidades): só dígitos e teclado `numeric`.
   */
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
 * Campo vazio é um estado válido (a pessoa apaga o "0" e digita por cima): NUNCA devolva `0`
 * para o estado a cada tecla (`|| 0`) — converta só no blur/submit.
 *
 *   <CurrencyInput value={amount} onChange={setAmount} placeholder="0,00" />
 *   <CurrencyInput value={km} onChange={setKm} decimals={0} />   // inteiro
 */
export function CurrencyInput({
  value,
  onChange,
  onBlur,
  onFocus,
  onMouseUp,
  decimals = 2,
  allowNegative = false,
  ...props
}: CurrencyInputProps) {
  const [touched, setTouched] = React.useState(false);
  // Marca "acabou de focar por clique/toque": o mouseup/touchend seguinte NÃO pode mover o cursor,
  // senão desfaz o select-all (comportamento do Safari/iOS).
  const justFocusedRef = React.useRef(false);
  const integerMode = decimals === 0;
  const invalid =
    touched &&
    value.trim() !== "" &&
    parseDecimalBR(value, { maxDecimals: decimals, allowNegative }) === null;

  return (
    <Input
      {...props}
      inputMode={integerMode ? "numeric" : "decimal"}
      enterKeyHint="done"
      autoComplete="off"
      value={value}
      aria-invalid={invalid || props["aria-invalid"] ? true : undefined}
      onFocus={(event) => {
        // Select-all ao tocar: quem digita por cima de "0"/valor antigo não precisa apagar nada.
        // No iOS o select() síncrono é descartado pelo próprio toque; precisa ir no próximo frame.
        const input = event.currentTarget;
        justFocusedRef.current = true;
        requestAnimationFrame(() => input.setSelectionRange(0, input.value.length));
        onFocus?.(event);
      }}
      onMouseUp={(event) => {
        if (justFocusedRef.current) event.preventDefault();
        justFocusedRef.current = false;
        onMouseUp?.(event);
      }}
      onChange={(event) => {
        // Inteiro descarta também "." e "," (colar "1.500" vira 1500).
        const allowed = integerMode
          ? allowNegative
            ? /[^\d-]/g
            : /\D/g
          : allowNegative
            ? /[^\d.,-]/g
            : /[^\d.,]/g;
        onChange(event.target.value.replace(allowed, ""));
      }}
      onBlur={(event) => {
        setTouched(true);
        justFocusedRef.current = false;
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
