"""Schemas de `/accounts/me`: preferências de interface da pessoa logada."""

from typing import Literal

from pydantic import BaseModel

# Espelha APP_STYLES em frontend/src/lib/appearance/app-styles.ts (um teste do front amarra os
# dois por snapshot do array). O prefixo `app-` é o slug do TEMPLATE: app novo renomeia
# `app-claro`/`app-escuro` para `<slug>-claro`/`<slug>-escuro` aqui, no front e no CSS.
# Estilo novo entra nos três lugares: este Literal, o catálogo do front e styles/themes/<id>.css.
AppStyleId = Literal[
    "app-claro",
    "nitido",
    "grafite",
    "areia",
    "app-escuro",
    "escuro-suave",
    "carbono",
    "alto-contraste",
]


class UiPreferencesPatch(BaseModel):
    app_style: AppStyleId


class UiPreferencesResponse(BaseModel):
    ui_preferences: dict


class AccountMeResponse(BaseModel):
    id: str
    ui_preferences: dict
