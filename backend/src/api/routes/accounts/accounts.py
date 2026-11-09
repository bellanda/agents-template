"""``/accounts/me``: identidade da sessão + preferências de interface (estilo visual).

O front pinta o estilo pelo cache local e só lê isto para seguir a conta em outro aparelho;
quem escolhe grava com o PATCH em background. Ver skill frontend, ref app-styles.
"""

from asyncpg.connection import Connection
from fastapi import APIRouter, Depends

from api.repositories.accounts.user_repository import user_repository
from api.schemas.accounts.accounts import (
    AccountMeResponse,
    UiPreferencesPatch,
    UiPreferencesResponse,
)
from api.services.auth import get_auth_context
from config.database import get_conn

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("/me", response_model=AccountMeResponse)
async def get_me(
    auth: dict = Depends(get_auth_context),
    conn: Connection = Depends(get_conn),
) -> AccountMeResponse:
    user_id: str = auth["user_id"]
    preferences = await user_repository.get_ui_preferences(conn, user_id)
    return AccountMeResponse(id=user_id, ui_preferences=preferences)


@router.patch("/me/ui-preferences", response_model=UiPreferencesResponse)
async def patch_ui_preferences(
    data: UiPreferencesPatch,
    auth: dict = Depends(get_auth_context),
    conn: Connection = Depends(get_conn),
) -> UiPreferencesResponse:
    preferences = await user_repository.set_app_style(conn, auth["user_id"], data.app_style)
    if data.font_size is not None:
        # The last write returns the final state, with both keys.
        preferences = await user_repository.set_font_size(conn, auth["user_id"], data.font_size)
    return UiPreferencesResponse(ui_preferences=preferences)
