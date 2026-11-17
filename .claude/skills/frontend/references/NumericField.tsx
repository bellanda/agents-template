import { FieldHint } from "@/components/forms/FieldHint";
import { CurrencyInput } from "@/components/ui/currency-input";
import { Label } from "@/components/ui/label";
import { parseDecimalBR } from "@/lib/utils/currency";
import { useState, type ComponentProps, type ReactNode } from "react";

interface NumericInputProps extends Omit<
  ComponentProps<typeof CurrencyInput>,
  "value" | "onChange" | "decimals" | "allowNegative" | "min" | "max" | "step"
> {
  value: number | null | undefined;
  /** `null` = campo vazio (ou ambíguo, ex. "1,500.00"). Quem usa decide: validar, manter o anterior ou salvar `null`. */
  onChange: (value: number | null) => void;
  min?: number;
  max?: number;
  /** Só define as casas decimais quando `decimals` não vem: step 1 (ou ausente) = inteiro, 0.1 = 1 casa, 0.01 = 2. */
  step?: number;
  /** Casas decimais aceitas (0 = inteiro). Default derivado de `step`. */
  decimals?: number;
}

interface NumericFieldProps extends NumericInputProps {
  label: string;
  hint?: ReactNode;
}

function decimalsFromStep(step: number | undefined): number {
  if (step === undefined || step >= 1) return 0;
  return Math.min(6, Math.ceil(-Math.log10(step)));
}

function toText(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "";
  // Valor guardado aparece como está ("18", "12,5"), sem zeros de enchimento nem arredondar.
  return String(value).replace(".", ",");
}

/**
 * Input numérico SEM rótulo (células de tabela, linhas de lista, rótulo próprio): mesma UX do
 * `NumericField`. Substitui o input HTML numérico nativo com `onChange` que devolvia `|| 0` (2026-11-17).
 *
 * O texto digitado fica em estado local, então apagar o "0" deixa o campo VAZIO (antes o
 * `onChange(Number(v) || 0)` devolvia 0 a cada tecla e ele nunca saía), o toque seleciona tudo e o
 * iPhone abre o teclado numérico. O pai recebe `number | null` a cada tecla; `null` = vazio.
 * Se o pai ignorar o `null` (mantém o valor anterior), o campo continua vazio durante a digitação e
 * volta ao valor do pai no blur — nunca reinsere o valor sob o dedo.
 */
export function NumericInput({
  value,
  onChange,
  min,
  max,
  step,
  decimals,
  onBlur,
  className,
  ...props
}: NumericInputProps) {
  const places = decimals ?? decimalsFromStep(step);
  const allowNegative = min === undefined || min < 0;
  const parse = (text: string) => {
    const parsed = parseDecimalBR(text, { maxDecimals: places, allowNegative });
    return parsed === null ? null : Number(parsed);
  };

  const [text, setText] = useState(() => toText(value));
  const [seenValue, setSeenValue] = useState(value ?? null);
  // Valor novo vindo do pai (reset do form, dado carregado) substitui o texto; eco do que a pessoa
  // acabou de digitar não, senão "1," viraria "1" no meio da digitação.
  if ((value ?? null) !== seenValue) {
    setSeenValue(value ?? null);
    if (parse(text) !== (value ?? null)) setText(toText(value));
  }

  const parsedNow = parse(text);
  const outOfRange =
    parsedNow !== null &&
    ((min !== undefined && parsedNow < min) || (max !== undefined && parsedNow > max));

  return (
    <CurrencyInput
      {...props}
      className={className ?? "h-10"}
      decimals={places}
      allowNegative={allowNegative}
      aria-invalid={outOfRange || props["aria-invalid"] ? true : undefined}
      value={text}
      onChange={(next) => {
        setText(next);
        onChange(parse(next));
      }}
      onBlur={(event) => {
        // Pai que não aceita vazio: devolve o valor dele em vez de deixar o campo em branco.
        if (parse(text) === null && value !== null && value !== undefined) {
          setText(toText(value));
        }
        onBlur?.(event);
      }}
    />
  );
}

/** Campo numérico canônico da frota (2026-11-17): rótulo + dica + `NumericInput`. */
export function NumericField({ label, hint, ...inputProps }: NumericFieldProps) {
  return (
    <div className="space-y-1.5">
      <Label className="flex h-5 items-center gap-1.5 text-sm">
        {label}
        {hint && <FieldHint>{hint}</FieldHint>}
      </Label>
      <NumericInput {...inputProps} />
    </div>
  );
}
