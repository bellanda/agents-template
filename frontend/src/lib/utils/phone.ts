/**
 * Telefone canônico da frota (padrão 2026-10-29) — CÓPIA IDÊNTICA em todo app, espelho de
 * `backend/src/api/core/phones.py`. Canônico = só dígitos com DDI, sem "+"; celular brasileiro
 * SEMPRE com o 9º dígito ("5535991107807"). A API grava e devolve o canônico; a tela SEMPRE
 * exibe por `formatPhone` e digita por `PhoneInput` (`ui/phone-input.tsx`), nunca o valor cru.
 * Origem: a Meta manda o `wa_id` de celulares antigos sem o 9 e a resposta à campanha virou outro
 * contato (kailos prod 2026-10-29). Mudou aqui? Mude o espelho Python no mesmo commit.
 */

const BR_COUNTRY_CODE = "55";
const DDD_END = 4; // "55" + DDD
const BR_LANDLINE_LENGTH = 12;
const BR_MOBILE_LENGTH = 13;
const NATIONAL_LANDLINE_LENGTH = 10;
const NATIONAL_MOBILE_LENGTH = 11;
const MOBILE_PREFIX = "9";
// O 9º dígito só foi acrescentado a celular (faixas 6-9 da época); fixo começa em 2-5.
const LEGACY_MOBILE_FIRST_DIGITS = "6789";
const LANDLINE_FIRST_DIGITS = "2345";
const FOREIGN_MIN_DIGITS = 8;
const FOREIGN_MAX_DIGITS = 15;

function canonicalBR(digits: string): string | null {
  const ddd = digits.slice(2, DDD_END);
  const subscriber = digits.slice(DDD_END);
  if (ddd.includes("0")) return null;
  if (digits.length === BR_MOBILE_LENGTH) {
    return subscriber.startsWith(MOBILE_PREFIX) ? digits : null;
  }
  if (LEGACY_MOBILE_FIRST_DIGITS.includes(subscriber[0])) {
    return digits.slice(0, DDD_END) + MOBILE_PREFIX + subscriber;
  }
  return LANDLINE_FIRST_DIGITS.includes(subscriber[0]) ? digits : null;
}

/**
 * Qualquer grafia -> canônico, ou null. "(35) 99110-7807", "+55 35 99110-7807" e
 * "553591107807" viram "5535991107807"; fixo "(34) 3210-1234" vira "553432101234".
 * Sem "+"/"00", 10-11 dígitos são DDD + número; o resto fica como estrangeiro. Idempotente.
 */
export function canonicalPhone(raw: string | null | undefined): string | null {
  const text = (raw ?? "").trim();
  const international = text.startsWith("+") || text.startsWith("00");
  const allDigits = text.replace(/\D/g, "");
  const digits = text.startsWith("00") ? allDigits.slice(2) : allDigits.replace(/^0+/, "");
  if (
    !international &&
    (digits.length === NATIONAL_LANDLINE_LENGTH || digits.length === NATIONAL_MOBILE_LENGTH)
  ) {
    const national = canonicalBR(BR_COUNTRY_CODE + digits);
    if (national) return national;
  }
  if (digits.startsWith(BR_COUNTRY_CODE)) {
    const brazilian = digits.length === BR_LANDLINE_LENGTH || digits.length === BR_MOBILE_LENGTH;
    return brazilian ? canonicalBR(digits) : null;
  }
  // Sem "+" também cai aqui: o canônico estrangeiro é gravado sem o sinal e volta igual.
  return digits.length >= FOREIGN_MIN_DIGITS && digits.length <= FOREIGN_MAX_DIGITS ? digits : null;
}

/**
 * Exibição única: "(35) 99110-7807", fixo "(34) 3210-1234", estrangeiro "+14155552671".
 * Aceita canônico ou grafia antiga; o que não é telefone volta como veio; vazio vira "".
 */
export function formatPhone(raw: string | null | undefined): string {
  const canonical = canonicalPhone(raw);
  if (!canonical) return raw ?? "";
  if (!canonical.startsWith(BR_COUNTRY_CODE)) return `+${canonical}`;
  const ddd = canonical.slice(2, DDD_END);
  const subscriber = canonical.slice(DDD_END);
  const split = subscriber.length - 4;
  return `(${ddd}) ${subscriber.slice(0, split)}-${subscriber.slice(split)}`;
}

/**
 * Dígitos que o `PhoneInput` mostra na máscara "(00) 00000-0000". Só o número completo com 55
 * (o que a API devolve) é convertido; o que está sendo digitado volta intacto — restaurar o 9
 * em "(35) 9911-0780" no meio da digitação trocaria o número.
 */
export function localPhoneDigits(raw: string | null | undefined): string {
  const digits = (raw ?? "").replace(/\D/g, "");
  const isFullBR =
    digits.startsWith(BR_COUNTRY_CODE) &&
    (digits.length === BR_LANDLINE_LENGTH || digits.length === BR_MOBILE_LENGTH);
  if (!isFullBR) return digits;
  return (canonicalBR(digits) ?? digits).slice(BR_COUNTRY_CODE.length);
}

/** Link "Abrir no WhatsApp" / `tel:`; null quando o número não é utilizável. */
export function whatsAppUrl(raw: string | null | undefined): string | null {
  const canonical = canonicalPhone(raw);
  return canonical ? `https://wa.me/${canonical}` : null;
}

export function telUrl(raw: string | null | undefined): string | null {
  const canonical = canonicalPhone(raw);
  return canonical ? `tel:+${canonical}` : null;
}

export const PHONE_INVALID_MESSAGE = "Telefone inválido: informe DDD + número.";
export const PHONE_MOBILE_INCOMPLETE_MESSAGE = "Celular tem 9 dígitos depois do DDD.";

/**
 * Erro do campo digitado (vazio = null; o form decide se é obrigatório). Mais estrito que o
 * backend: digitando, DDD + 8 dígitos começando em 6-9 é celular pela METADE, não celular antigo
 * — o backend restaura o 9 só para planilha/`wa_id`, onde a grafia antiga é dado real.
 */
export function phoneFieldError(raw: string | null | undefined): string | null {
  const text = (raw ?? "").trim();
  if (!text.replace(/\D/g, "")) return null;
  if (text.startsWith("+") || text.startsWith("00")) {
    return canonicalPhone(text) ? null : PHONE_INVALID_MESSAGE;
  }
  // O `PhoneInput` é só Brasil: o que ele carrega/emite tem de fechar como DDD + número.
  const local = localPhoneDigits(text);
  if (local.length === NATIONAL_LANDLINE_LENGTH && LEGACY_MOBILE_FIRST_DIGITS.includes(local[2])) {
    return PHONE_MOBILE_INCOMPLETE_MESSAGE;
  }
  const isNational =
    local.length === NATIONAL_LANDLINE_LENGTH || local.length === NATIONAL_MOBILE_LENGTH;
  return isNational && canonicalBR(BR_COUNTRY_CODE + local) ? null : PHONE_INVALID_MESSAGE;
}
