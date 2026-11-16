"""Contract guard for the FastAPI 0.162+ change (U2, 2026-11-15): an omitted boolean form field no
longer silently defaults to False. A route that wants "unchecked checkbox = False" must declare the
default explicitly; one without a default must reject the request. Pure framework behaviour, no DB."""

from typing import Annotated

import httpx
from fastapi import FastAPI, Form

app = FastAPI()


@app.post("/explicit")
async def explicit(flag: Annotated[bool, Form()] = False) -> dict[str, bool]:
    return {"flag": flag}


@app.post("/required")
async def required(flag: Annotated[bool, Form()]) -> dict[str, bool]:
    return {"flag": flag}


async def test_omitted_bool_form_field_follows_declared_default() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.post("/explicit", data={})).json() == {"flag": False}
        assert (await c.post("/explicit", data={"flag": "true"})).json() == {"flag": True}
        assert (await c.post("/required", data={})).status_code == 422
        assert (await c.post("/required", data={"flag": "true"})).json() == {"flag": True}
