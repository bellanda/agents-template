"""Chunked upload sessions (canonical test, byte-identical across the fleet).

Regression: prod 2026-11-16, a 38 MB iPhone video got 413 from nginx (20 MB per REQUEST). It now
travels as 8 MiB chunks to an upload session and domain routes consume it by `file_upload_id`.
App-agnostic: tiny FastAPI app built from the factories, fake auth header, tmp staging dir.
"""

import json
import time

import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile

from api.services.uploads import upload_sessions as sessions
from config.api import api_config

CHUNK = 1024
MIB = 1024 * 1024


async def fake_user_key(request: Request) -> str:
    user = request.headers.get("x-user")
    if not user:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    return user


@pytest.fixture
def staging(tmp_path, monkeypatch):
    monkeypatch.setattr(api_config, "UPLOAD_STAGING_DIR", tmp_path)
    monkeypatch.setattr(api_config, "UPLOAD_CHUNK_BYTES", CHUNK)
    return tmp_path


# Mounted where every app mounts it, so the write-route coverage guard (tests/write_route_coverage.py)
# counts these hits as the app's real `/api/v1/upload-sessions` routes (CRUD audit 2026-11-17).
API_PREFIX = "/api/v1"


@pytest.fixture
def app(staging):
    app = FastAPI()
    app.include_router(sessions.build_upload_sessions_router(fake_user_key), prefix=API_PREFIX)
    staged = sessions.make_staged_or_direct_file(fake_user_key)

    @app.post(f"{API_PREFIX}/consume")
    async def consume(file: UploadFile = Depends(staged), fail: bool = False) -> dict:
        body = await file.read()
        if fail:
            raise HTTPException(status_code=422, detail="boom")
        return {"size": len(body), "name": file.filename, "mime": file.content_type}

    return app


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=f"http://t{API_PREFIX}") as http:
        yield http


async def create(client, size, *, user="1", mime="video/mp4", name="v.mp4"):
    return await client.post(
        "/upload-sessions",
        json={"filename": name, "mime_type": mime, "size_bytes": size},
        headers={"x-user": user},
    )


async def put(client, session_id, offset, data, *, user="1"):
    return await client.put(
        f"/upload-sessions/{session_id}",
        params={"offset": offset},
        content=data,
        headers={"x-user": user, "content-type": "application/octet-stream"},
    )


async def test_chunked_upload_resume_and_consume_discards_only_on_success(client, staging):
    payload = bytes(range(256)) * 20  # 5120 bytes = 5 chunks of 1024
    created = await create(client, len(payload))
    assert created.status_code == 201
    body = created.json()
    assert body["chunk_bytes"] == CHUNK and body["offset"] == 0
    sid = body["id"]

    assert (await put(client, sid, 0, payload[:CHUNK])).json() == {"offset": CHUNK}
    # "Connection dropped": the client asks where the server is and resumes from there.
    status = (await client.get(f"/upload-sessions/{sid}", headers={"x-user": "1"})).json()
    assert status["offset"] == CHUNK and status["state"] == "uploading" and status["error"] is None
    for start in range(CHUNK, len(payload), CHUNK):
        res = await put(client, sid, start, payload[start : start + CHUNK])
        assert res.status_code == 200
    status = (await client.get(f"/upload-sessions/{sid}", headers={"x-user": "1"})).json()
    assert status["state"] == "complete" and status["offset"] == len(payload)

    # A failing endpoint keeps the session so the retry reuses the uploaded bytes ...
    form = {"file_upload_id": sid}
    failed = await client.post("/consume?fail=true", data=form, headers={"x-user": "1"})
    assert failed.status_code == 422
    assert (await client.get(f"/upload-sessions/{sid}", headers={"x-user": "1"})).status_code == 200
    # ... a successful one gets the right bytes/name/mime and discards it.
    ok = await client.post("/consume", data=form, headers={"x-user": "1"})
    assert ok.json() == {"size": len(payload), "name": "v.mp4", "mime": "video/mp4"}
    assert (await client.get(f"/upload-sessions/{sid}", headers={"x-user": "1"})).status_code == 404


async def test_38_mb_file_goes_through_as_five_chunks(client, monkeypatch):
    monkeypatch.setattr(api_config, "UPLOAD_CHUNK_BYTES", 8 * MIB)
    size = 38 * MIB
    created = (await create(client, size)).json()
    assert created["chunk_bytes"] == 8 * MIB
    sent = 0
    chunks = 0
    while sent < size:
        length = min(8 * MIB, size - sent)
        res = await put(client, created["id"], sent, b"x" * length)
        assert res.status_code == 200
        sent += length
        chunks += 1
    assert chunks == 5
    status = (await client.get(f"/upload-sessions/{created['id']}", headers={"x-user": "1"})).json()
    assert status["state"] == "complete" and status["offset"] == size


async def test_offset_mismatch_is_409_with_server_offset_and_duplicate_is_idempotent(client):
    sid = (await create(client, 3 * CHUNK)).json()["id"]
    await put(client, sid, 0, b"a" * CHUNK)

    wrong = await put(client, sid, 2 * CHUNK, b"b" * CHUNK)
    assert wrong.status_code == 409
    assert wrong.json()["offset"] == CHUNK and isinstance(wrong.json()["detail"], str)

    again = await put(client, sid, 0, b"a" * CHUNK)  # retry of a chunk already on disk
    assert again.status_code == 200 and again.json() == {"offset": CHUNK}
    status = (await client.get(f"/upload-sessions/{sid}", headers={"x-user": "1"})).json()
    assert status["offset"] == CHUNK  # not appended twice


async def test_overflow_is_400_and_discards_the_session(client):
    sid = (await create(client, CHUNK)).json()["id"]
    await put(client, sid, 0, b"a" * (CHUNK // 2))

    res = await put(client, sid, CHUNK // 2, b"a" * CHUNK)

    assert res.status_code == 400
    assert (await client.get(f"/upload-sessions/{sid}", headers={"x-user": "1"})).status_code == 404


async def test_chunk_bigger_than_chunk_bytes_is_413(client):
    sid = (await create(client, 10 * CHUNK)).json()["id"]

    assert (await put(client, sid, 0, b"a" * (CHUNK + 1))).status_code == 413


async def test_other_users_session_is_404_on_every_verb_and_only_the_owner_deletes(client):
    sid = (await create(client, CHUNK, user="1")).json()["id"]

    assert (await put(client, sid, 0, b"a", user="2")).status_code == 404
    assert (await client.get(f"/upload-sessions/{sid}", headers={"x-user": "2"})).status_code == 404
    bogus = await client.post("/consume", data={"file_upload_id": sid}, headers={"x-user": "2"})
    assert bogus.status_code == 404
    # DELETE of someone else's session used to answer 204 ("deleted") while nothing happened
    # (CRUD audit 2026-11-17, user decision: answer "não encontrado").
    assert (
        await client.delete(f"/upload-sessions/{sid}", headers={"x-user": "2"})
    ).status_code == 404
    assert (await client.get(f"/upload-sessions/{sid}", headers={"x-user": "1"})).status_code == 200
    assert (
        await client.delete(f"/upload-sessions/{sid}", headers={"x-user": "1"})
    ).status_code == 204
    assert (await client.get(f"/upload-sessions/{sid}", headers={"x-user": "1"})).status_code == 404
    assert (
        await client.delete(f"/upload-sessions/{sid}", headers={"x-user": "1"})
    ).status_code == 404


async def test_oversize_create_is_413_per_category_and_auth_is_required(client, monkeypatch):
    monkeypatch.setattr(api_config, "IMAGE_MAX_BYTES", 2 * MIB)
    monkeypatch.setattr(api_config, "FILE_MAX_BYTES", 5 * MIB)

    image = await create(client, 3 * MIB, mime="image/jpeg", name="a.jpg")
    video = await create(client, 6 * MIB)

    assert image.status_code == 413
    assert image.json()["detail"] == "Arquivo muito grande (3 MB). Máximo: 2 MB."
    assert video.status_code == 413 and "Máximo: 5 MB" in video.json()["detail"]
    assert (
        await client.post("/upload-sessions", json={"filename": "a", "size_bytes": 1})
    ).status_code == 401


async def test_quota_and_expired_sessions_are_swept(client, staging, monkeypatch):
    monkeypatch.setattr(sessions, "MAX_OPEN_SESSIONS_PER_USER", 2)
    first = (await create(client, CHUNK)).json()["id"]
    await create(client, CHUNK)
    assert (await create(client, CHUNK)).status_code == 429
    assert (await create(client, CHUNK, user="2")).status_code == 201  # per user

    monkeypatch.setattr(sessions, "MAX_STAGED_BYTES_PER_USER", 10)
    assert (await create(client, 100, user="3")).status_code == 429  # staged-bytes quota

    # Expire the first session: the next create sweeps it and the slot frees up.
    monkeypatch.setattr(sessions, "MAX_STAGED_BYTES_PER_USER", 2 * 1024 * MIB)
    meta = staging / "1" / first / sessions.META_NAME
    raw = json.loads(meta.read_text())
    raw["expires_at"] = time.time() - 5
    meta.write_text(json.dumps(raw))
    assert (await create(client, CHUNK)).status_code == 201
    assert not (staging / "1" / first).exists()


async def test_prepared_artifact_is_what_the_consumer_sees(client, staging):
    sid = (await create(client, 4, mime="video/quicktime", name="v.mov")).json()["id"]
    await put(client, sid, 0, b"orig")
    await sessions.mark_processing("1", sid)
    artifact = staging / "converted.mp4"
    artifact.write_bytes(b"converted-mp4")
    await sessions.store_prepared("1", sid, artifact, "video/mp4", "v.mp4")

    status = (await client.get(f"/upload-sessions/{sid}", headers={"x-user": "1"})).json()
    ok = await client.post("/consume", data={"file_upload_id": sid}, headers={"x-user": "1"})

    assert status["state"] == "ready"
    assert ok.json() == {"size": len(b"converted-mp4"), "name": "v.mp4", "mime": "video/mp4"}


async def test_failed_session_reports_ptbr_error_and_is_not_consumable(client):
    sid = (await create(client, 4)).json()["id"]
    await put(client, sid, 0, b"data")
    await sessions.mark_failed("1", sid, "Vídeo longo demais.")

    status = (await client.get(f"/upload-sessions/{sid}", headers={"x-user": "1"})).json()
    res = await client.post("/consume", data={"file_upload_id": sid}, headers={"x-user": "1"})

    assert status["state"] == "failed" and status["error"] == "Vídeo longo demais."
    assert res.status_code == 400 and res.json()["detail"] == "Vídeo longo demais."
