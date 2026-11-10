"""Schemas de `/accounts/me`: preferências de interface da pessoa logada."""

from typing import Literal

from pydantic import BaseModel

# Espelha APP_STYLES em frontend/src/lib/appearance/app-styles.ts (um teste do front amarra os
# dois por snapshot do array). `app-claro`/`app-escuro` saíram em 2026-11-10: Nítido e Escuro
# suave são o par padrão.
# Estilo novo entra nos três lugares: este Literal, o catálogo do front e styles/themes/<id>.css.
AppStyleId = Literal[
    "nitido",
    "grafite",
    "areia",
    "escuro-suave",
    "carbono",
    "alto-contraste",
]

# Mirrors `FONT_SIZES` in `frontend/src/lib/appearance/font-size.ts`: a new id goes in both.
FontSizeId = Literal["padrao", "grande", "muito-grande"]


class UiPreferencesPatch(BaseModel):
    app_style: AppStyleId
    font_size: FontSizeId | None = None  # absent = keeps what is saved


class UiPreferencesResponse(BaseModel):
    ui_preferences: dict


class AccountMeResponse(BaseModel):
    id: str
    ui_preferences: dict
