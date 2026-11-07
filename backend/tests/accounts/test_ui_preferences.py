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


async def test_unknown_style_is_rejected_with_422(client):
    res = await client.patch(PATCH, headers=USER, json={"app_style": "neon"})
    assert res.status_code == 422
    assert (await client.get(ME, headers=USER)).json()["ui_preferences"] == {}


async def test_patch_keeps_other_preference_keys_and_other_users_untouched(client, db_conn):
    await client.patch(PATCH, headers=USER, json={"app_style": "carbono"})
    await db_conn.execute(
        'UPDATE users SET ui_preferences = ui_preferences || \'{"help_seen": ["home"]}\'::jsonb '
        "WHERE id = 'pessoa-1'"
    )
    other = {"X-User-Id": "pessoa-2"}
    await client.patch(PATCH, headers=other, json={"app_style": "areia"})

    res = await client.patch(PATCH, headers=USER, json={"app_style": "escuro-suave"})

    assert res.json()["ui_preferences"] == {"app_style": "escuro-suave", "help_seen": ["home"]}
    assert (await client.get(ME, headers=other)).json()["ui_preferences"] == {"app_style": "areia"}
