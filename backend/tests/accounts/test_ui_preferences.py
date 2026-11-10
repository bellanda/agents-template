"""`PATCH /accounts/me/ui-preferences` + `GET /accounts/me`: estilo visual por pessoa.

Rota montada num FastAPI nu (o lifespan do app real sobe NATS/Postgres) com `get_conn` apontado
para a conexão transacional do teste, que faz rollback no fim de cada caso.
"""

import httpx
import pytest
from fastapi import FastAPI

from api.routes.accounts import router
from config.database import get_conn

ME = "/accounts/me"
PATCH = "/accounts/me/ui-preferences"
USER = {"X-User-Id": "pessoa-1"}


@pytest.fixture
async def client(db_conn):
    app = FastAPI()
    app.include_router(router)

    async def conn_override():
        yield db_conn

    app.dependency_overrides[get_conn] = conn_override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def test_valid_style_is_saved_and_comes_back_on_me(client):
    assert (await client.get(ME, headers=USER)).json()["ui_preferences"] == {}

    res = await client.patch(PATCH, headers=USER, json={"app_style": "nitido"})
    assert res.status_code == 200
    assert res.json()["ui_preferences"]["app_style"] == "nitido"

    me = (await client.get(ME, headers=USER)).json()
    assert me["id"] == "pessoa-1"
    assert me["ui_preferences"]["app_style"] == "nitido"


@pytest.mark.parametrize("style", ["nitido", "escuro-suave", "carbono"])
async def test_each_catalog_style_is_accepted(client, style):
    res = await client.patch(PATCH, headers=USER, json={"app_style": style})
    assert res.status_code == 200, res.text


# `app-claro`/`app-escuro` were replaced by Nítido/Escuro suave (2026-11-10).
@pytest.mark.parametrize("style", ["neon", "app-claro", "app-escuro"])
async def test_unknown_or_removed_style_is_rejected_with_422(client, style):
    res = await client.patch(PATCH, headers=USER, json={"app_style": style})
    assert res.status_code == 422
    assert (await client.get(ME, headers=USER)).json()["ui_preferences"] == {}


async def test_patch_keeps_other_preference_keys_and_other_users_untouched(client, db_conn):
    await client.patch(PATCH, headers=USER, json={"app_style": "escuro-suave"})
    await db_conn.execute(
        'UPDATE users SET ui_preferences = ui_preferences || \'{"help_seen": ["home"]}\'::jsonb '
        "WHERE id = 'pessoa-1'"
    )
    other = {"X-User-Id": "pessoa-2"}
    await client.patch(PATCH, headers=other, json={"app_style": "nitido"})

    res = await client.patch(PATCH, headers=USER, json={"app_style": "escuro-suave"})

    assert res.json()["ui_preferences"] == {"app_style": "escuro-suave", "help_seen": ["home"]}
    assert (await client.get(ME, headers=other)).json()["ui_preferences"] == {"app_style": "nitido"}


async def test_font_size_is_saved_with_the_style_without_erasing_other_keys(client, db_conn):
    """The dialog saves style and font size together; neither may erase what was already saved."""
    await client.patch(PATCH, headers=USER, json={"app_style": "escuro-suave"})
    await db_conn.execute(
        'UPDATE users SET ui_preferences = ui_preferences || \'{"help_seen": ["home"]}\'::jsonb '
        "WHERE id = 'pessoa-1'"
    )
    res = await client.patch(
        PATCH, headers=USER, json={"app_style": "nitido", "font_size": "grande"}
    )

    assert res.status_code == 200
    assert res.json()["ui_preferences"] == {
        "app_style": "nitido",
        "font_size": "grande",
        "help_seen": ["home"],
    }
    assert (await client.get(ME, headers=USER)).json()["ui_preferences"]["font_size"] == "grande"


async def test_unknown_font_size_is_rejected_with_422(client):
    res = await client.patch(
        PATCH, headers=USER, json={"app_style": "nitido", "font_size": "gigante"}
    )
    assert res.status_code == 422
