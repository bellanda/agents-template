"""Telefone canônico da frota — CÓPIA IDÊNTICA em todo app (espelho de `phone.test.ts`)."""

import pytest
from pydantic import BaseModel, ValidationError

from api.core.phones import (
    OptionalPhoneNumber,
    PhoneNumber,
    canonical_phone,
    is_br_mobile,
    phone_lookup_variants,
)

CASES = [
    # Regressão kailos prod 2026-10-29: o `wa_id` sem o 9 é a MESMA linha da planilha com o 9.
    ("+553591107807", "5535991107807"),
    ("553591107807", "5535991107807"),
    ("5535991107807", "5535991107807"),
    ("(35) 99110-7807", "5535991107807"),
    ("+55 35 99110-7807", "5535991107807"),
    ("0055 35 99110-7807", "5535991107807"),  # discagem internacional 00
    ("035991107807", "5535991107807"),  # 0 de longa distância
    ("(35) 9110-7807", "5535991107807"),  # celular antigo de planilha
    ("(34) 3210-1234", "553432101234"),  # fixo: nunca ganha o 9
    ("553432101234", "553432101234"),
    ("55 (55) 99123-4567", "5555991234567"),  # DDD 55 (Santa Maria/RS)
    ("55991234567", "5555991234567"),
    ("+1 415 555 2671", "14155552671"),  # estrangeiro: dígitos como vieram
    ("14155552671", "14155552671"),  # canônico estrangeiro relido (idempotente)
    ("5535191107807", None),  # 13 dígitos sem o 9 do celular
    ("+55 10 99110-7807", None),  # DDD com zero
    ("190", None),
    ("", None),
    (None, None),
]


@pytest.mark.parametrize(("raw", "expected"), CASES, ids=[str(raw) for raw, _ in CASES])
def test_canonical_phone(raw, expected):
    assert canonical_phone(raw) == expected
    if expected:
        assert canonical_phone(expected) == expected  # idempotente: a API devolve e recebe isto


def test_lookup_variants_find_rows_saved_before_the_standard():
    assert phone_lookup_variants("553591107807") == [
        "5535991107807",
        "35991107807",
        "553591107807",
        "3591107807",
    ]
    assert phone_lookup_variants("(34) 3210-1234") == ["553432101234", "3432101234"]
    assert phone_lookup_variants("+14155552671") == ["14155552671"]
    assert is_br_mobile("5535991107807") and not is_br_mobile("553432101234")


def test_schema_types_store_the_canonical_and_refuse_garbage():
    class Form(BaseModel):
        phone: PhoneNumber
        other: OptionalPhoneNumber = None

    assert Form(phone="(35) 99110-7807", other="  ").model_dump() == {
        "phone": "5535991107807",
        "other": None,
    }
    with pytest.raises(ValidationError, match="Telefone inválido"):
        Form(phone="123")
    with pytest.raises(ValidationError, match="Informe o telefone"):
        Form(phone="")
