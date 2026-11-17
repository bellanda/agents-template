"""Self-test of the write-route coverage guard (fleet canonical, shared-backend, 2026-11-17).

Proves the two halves the guard relies on: the recorder counts a successful write under its FULL
prefixed path (and ignores 4xx and reads), and the verdict makes the baseline only shrink.
"""

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from tests.write_route_coverage import (
    collect_write_routes,
    evaluate_write_route_coverage,
    install_write_route_recorder,
    recorded_write_hits,
)

ITEM_PATH = "/api/items/{item_id}"


def make_items_app() -> FastAPI:
    router = APIRouter(prefix="/items")

    @router.post("/{item_id}", status_code=201)
    async def create_item(item_id: int) -> dict:
        return {"id": item_id}

    @router.patch("/{item_id}")
    async def refuse_item(item_id: int) -> dict:
        raise HTTPException(status_code=403, detail=f"item {item_id} is read-only")

    @router.get("/{item_id}")
    async def read_item(item_id: int) -> dict:
        return {"id": item_id}

    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.mark.asyncio
async def test_recorder_counts_only_successful_writes_under_the_full_path():
    app = make_items_app()
    install_write_route_recorder()
    recorded_write_hits.difference_update(collect_write_routes(app.routes))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/items/7")
        refused = await client.patch("/api/items/7")
        await client.get("/api/items/7")

    assert (created.status_code, refused.status_code) == (201, 403)
    assert collect_write_routes(app.routes) == {f"POST {ITEM_PATH}", f"PATCH {ITEM_PATH}"}
    assert f"POST {ITEM_PATH}" in recorded_write_hits
    assert f"PATCH {ITEM_PATH}" not in recorded_write_hits
    recorded_write_hits.difference_update(collect_write_routes(app.routes))


def test_baseline_only_shrinks_and_every_entry_needs_a_reason():
    expected = {"POST /a", "PATCH /b", "DELETE /c", "PUT /d", "PUT /e"}
    hits = {"POST /a", "PUT /d"}
    baseline = {
        "PATCH /b": "webhook: covered by the signature test",
        "PUT /d": "was uncovered",
        "POST /gone": "route removed",
        "PUT /e": " ",
    }

    verdict = evaluate_write_route_coverage(expected, hits, baseline)

    assert verdict.uncovered_new == ["DELETE /c"]
    assert verdict.baseline_now_covered == ["PUT /d"]
    assert verdict.baseline_vanished == ["POST /gone"]
    assert verdict.baseline_missing_reason == ["PUT /e"]
    assert not verdict.is_clean
    clean = evaluate_write_route_coverage({"POST /a"}, {"POST /a"}, {})
    assert clean.is_clean
