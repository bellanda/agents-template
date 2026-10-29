"""Telefone canônico da frota (padrão 2026-10-29) — CÓPIA IDÊNTICA em todo app.

Canônico = só dígitos com DDI, sem "+" (E.164 sem o sinal). Brasil: `55` + DDD + número, e
celular SEMPRE com o 9º dígito. É o valor que se grava, compara e devolve na API; a tela formata
na exibição (`lib/utils/phone.ts`). Toda entrada passa por aqui: formulário (`PhoneNumber` no
schema), planilha/importação, lead de portal, webhook da Meta (`canonical_phone("+" + wa_id)`).

Por quê: a Meta manda o `wa_id` de celulares antigos SEM o 9 (`553591107807`) e a planilha traz
COM o 9 (`5535991107807`); comparar o cru separou a resposta da campanha do contato que recebeu o
template (kailos prod 2026-10-29, "Alves imports"). Linha guardada antes do padrão pode estar em
outra grafia: busca por telefone usa `phone_lookup_variants`.
Mudou aqui? Mude o espelho `frontend/src/lib/utils/phone.ts` e o SQL da migration de normalização
(skill `integrations` → `references/phone-numbers.md`) no mesmo commit.
"""

from typing import Annotated, Final

from pydantic import BeforeValidator

BR_COUNTRY_CODE: Final = "55"
INTERNATIONAL_PREFIXES: Final = ("+", "00")
DDD_END: Final = 4  # "55" + DDD de 2 dígitos
BR_LANDLINE_LENGTH: Final = 12  # 55 + DDD + 8 (fixo, ou celular antigo sem o 9)
BR_MOBILE_LENGTH: Final = 13  # 55 + DDD + 9 + 8
NATIONAL_LANDLINE_LENGTH: Final = 10  # DDD + 8
NATIONAL_MOBILE_LENGTH: Final = 11  # DDD + 9 + 8
MOBILE_PREFIX: Final = "9"
# O 9º dígito só foi acrescentado a CELULAR (faixas 6-9 da época). Fixo começa em 2-5: um 9 na
# frente dele viraria outra linha, que passaria a valer como identidade de alguém.
LEGACY_MOBILE_FIRST_DIGITS: Final = frozenset("6789")
LANDLINE_FIRST_DIGITS: Final = frozenset("2345")
FOREIGN_MIN_DIGITS: Final = 8
FOREIGN_MAX_DIGITS: Final = 15  # teto do E.164
INVALID_PHONE_MESSAGE: Final = "Telefone inválido: informe DDD + número, ex.: (35) 99110-7807."
REQUIRED_PHONE_MESSAGE: Final = "Informe o telefone."


def _canonical_br(digits: str) -> str | None:
    """`55…` com 12/13 dígitos -> canônico, ou None quando não é número brasileiro válido."""
    ddd, subscriber = digits[2:DDD_END], digits[DDD_END:]
    if "0" in ddd:
        return None
    if len(digits) == BR_MOBILE_LENGTH:
        return digits if subscriber.startswith(MOBILE_PREFIX) else None
    if subscriber[0] in LEGACY_MOBILE_FIRST_DIGITS:
        return digits[:DDD_END] + MOBILE_PREFIX + subscriber
    return digits if subscriber[0] in LANDLINE_FIRST_DIGITS else None


def canonical_phone(raw: object) -> str | None:
    """Qualquer grafia -> canônico, ou None quando não identifica um telefone.

    "(35) 99110-7807", "+55 35 99110-7807", "035991107807" e "553591107807" viram
    "5535991107807"; fixo "(34) 3210-1234" vira "553432101234". Sem "+"/"00", 10-11 dígitos são
    DDD + número; o que não fecha como brasileiro fica como estrangeiro (dígitos como vieram).
    Idempotente: `canonical_phone(canonical_phone(x)) == canonical_phone(x)`. O webhook da Meta
    passa `"+" + wa_id`, que já traz o DDI.
    """
    text = str(raw or "").strip()
    international = text.startswith(INTERNATIONAL_PREFIXES)
    digits = "".join(ch for ch in text if ch.isdigit())
    digits = digits[2:] if text.startswith("00") else digits.lstrip("0")
    if not international and len(digits) in (NATIONAL_LANDLINE_LENGTH, NATIONAL_MOBILE_LENGTH):
        national = _canonical_br(BR_COUNTRY_CODE + digits)
        if national:
            return national
    if digits.startswith(BR_COUNTRY_CODE):
        if len(digits) in (BR_LANDLINE_LENGTH, BR_MOBILE_LENGTH):
            return _canonical_br(digits)
        return None
    # Sem "+" também cai aqui: o canônico estrangeiro é gravado sem o sinal e tem de voltar igual
    # (idempotente). EUA não colide com DDD+celular: o 2º dígito do código de área nunca é 9.
    return digits if FOREIGN_MIN_DIGITS <= len(digits) <= FOREIGN_MAX_DIGITS else None


def phone_lookup_variants(raw: object) -> list[str]:
    """Grafias em que o MESMO número pode estar gravado, canônico primeiro.

    Para `WHERE phone = ANY($n::text[]) ORDER BY array_position($n::text[], phone::text)`: acha a
    linha gravada antes do padrão (sem o 9, sem o 55) e prefere a canônica quando há as duas.
    """
    canonical = canonical_phone(raw)
    if canonical is None:
        digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
        return [digits] if digits else []
    if not canonical.startswith(BR_COUNTRY_CODE):
        return [canonical]
    variants = [canonical, canonical[len(BR_COUNTRY_CODE) :]]
    subscriber = canonical[DDD_END:]
    if len(canonical) == BR_MOBILE_LENGTH and subscriber[1] in LEGACY_MOBILE_FIRST_DIGITS:
        legacy = canonical[:DDD_END] + subscriber[1:]
        variants += [legacy, legacy[len(BR_COUNTRY_CODE) :]]
    return variants


def is_br_mobile(phone: str | None) -> bool:
    """Canônico de celular brasileiro (o único que recebe WhatsApp com certeza)."""
    return bool(phone) and len(phone) == BR_MOBILE_LENGTH and phone.startswith(BR_COUNTRY_CODE)


def _optional_phone(value: object) -> str | None:
    if value is None or not str(value).strip():
        return None
    canonical = canonical_phone(value)
    if canonical is None:
        raise ValueError(INVALID_PHONE_MESSAGE)
    return canonical


def _required_phone(value: object) -> str:
    canonical = _optional_phone(value)
    if canonical is None:
        raise ValueError(REQUIRED_PHONE_MESSAGE)
    return canonical


# Campo de telefone em schema de entrada: aceita qualquer grafia e guarda o canônico.
PhoneNumber = Annotated[str, BeforeValidator(_required_phone)]
OptionalPhoneNumber = Annotated[str | None, BeforeValidator(_optional_phone)]
