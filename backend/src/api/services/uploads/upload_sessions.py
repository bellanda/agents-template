"""Chunked upload sessions: the only way a big file reaches the backend.

CANONICAL FILE, byte-identical in every fleet app. Edit it in
``/mnt/c/Users/gusta/OneDrive/Config Files/agents/shared-backend/canonical/`` and propagate with
``rules.py``; never edit one app's copy. Only stdlib, anyio, structlog, fastapi/starlette and
``config.api`` are imported, so the per-app adapter injects auth (a ``user_key`` dependency).

Why: every app sits behind Cloudflare (100 MB per request, ~100 s origin timeout -> 524) and an
nginx that caps each REQUEST at 20 MB, and the backend ``/tmp`` is a 64 MB tmpfs. A 38 MB iPhone
video sent in one request died with 413 (prod 2026-11-16). The per-REQUEST limit is a transport
fact; the per-FILE limit is ours (``api_config.IMAGE_MAX_BYTES`` / ``FILE_MAX_BYTES``).

Protocol (the frontend uploader codes against exactly this):
- ``POST /upload-sessions`` ``{filename, mime_type, size_bytes}`` -> 201 ``{id, chunk_bytes, offset,
  expires_at}``. 413 when the file is over its category limit, 429 over the per-user quota.
- ``PUT /upload-sessions/{id}?offset=N`` raw body <= ``chunk_bytes`` -> 200 ``{offset}``. The body is
  streamed straight to disk (no multipart, never ``/tmp``). A wrong offset is 409
  ``{"detail", "offset"}`` with the real one; a chunk already on disk is idempotent (200).
- ``GET /upload-sessions/{id}`` -> ``{id, offset, size_bytes, state, error}`` (resume + polling).
  ``state``: uploading | complete | processing | ready | failed.
- ``DELETE /upload-sessions/{id}`` -> 204.
- Domain routes take the form field ``file_upload_id`` INSTEAD of ``file``
  (``make_staged_or_direct_file``); the session is discarded only when the endpoint succeeds, so a
  failed request can be retried with the same id.

Layout: ``UPLOAD_STAGING_DIR/{user_key}/{session_id}/{meta.json,data,prepared,lock}``. Granian runs
several worker processes, so every mutation happens under ``fcntl.flock`` on ``lock``. A session
belongs to one user: another user's id is simply "not found". Sessions expire after
``SESSION_TTL_SECONDS`` of inactivity and are swept at startup and on every create.
"""

import contextlib
import fcntl
import json
import math
import mimetypes
import os
import re
import shutil
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

import anyio
import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.datastructures import Headers

from config.api import api_config

log = structlog.get_logger(__name__)

SESSION_TTL_SECONDS: Final = 6 * 60 * 60
MAX_OPEN_SESSIONS_PER_USER: Final = 10
MAX_STAGED_BYTES_PER_USER: Final = 2 * 1024 * 1024 * 1024
# A background conversion that never reports back (worker restarted) must not leave the client
# polling forever: past this age a "processing" session is reported as failed.
PROCESSING_STALE_SECONDS: Final = 20 * 60
# Shared scratch area (ffmpeg workdirs). Starts with "." so it can never collide with a user key.
WORK_DIR_NAME: Final = ".work"
META_NAME: Final = "meta.json"
DATA_NAME: Final = "data"
PREPARED_NAME: Final = "prepared"
LOCK_NAME: Final = "lock"
COPY_BUFFER_BYTES: Final = 1024 * 1024
BYTES_PER_MEGABYTE: Final = 1024 * 1024
SESSION_ID_RE: Final = re.compile(r"^[0-9a-f]{32}$")
USER_KEY_UNSAFE_RE: Final = re.compile(r"[^A-Za-z0-9_-]")

SessionState = Literal["uploading", "complete", "processing", "ready", "failed"]
SessionPhase = Literal["open", "processing", "ready", "failed"]

NOT_FOUND_DETAIL: Final = "Envio não encontrado ou expirado. Envie o arquivo de novo."


class OffsetMismatchError(Exception):
    """The chunk does not continue where the server stopped; ``offset`` is where it did."""

    def __init__(self, offset: int) -> None:
        super().__init__(f"chunk offset does not match the staged size (server is at {offset})")
        self.offset = offset


@dataclass(frozen=True)
class UploadSession:
    id: str
    user_key: str
    filename: str
    mime_type: str
    size_bytes: int
    created_at: float
    expires_at: float
    phase: SessionPhase = "open"
    error: str | None = None
    prepared_mime: str | None = None
    prepared_filename: str | None = None
    processing_since: float | None = None
    # Bytes on disk right now. Derived from the data file on every load, never persisted.
    offset: int = 0

    @property
    def state(self) -> SessionState:
        if self.phase == "open":
            return "complete" if self.offset >= self.size_bytes else "uploading"
        stale = (
            self.phase == "processing"
            and self.processing_since is not None
            and time.time() - self.processing_since > PROCESSING_STALE_SECONDS
        )
        return "failed" if stale else self.phase

    @property
    def public_error(self) -> str | None:
        if self.phase == "processing" and self.state == "failed":
            return "A conversão do vídeo demorou demais. Envie o vídeo de novo."
        return self.error

    @property
    def is_ready_to_consume(self) -> bool:
        return self.state in ("complete", "ready")


class CreateUploadSessionRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(default="application/octet-stream", max_length=255)
    size_bytes: int = Field(gt=0)


# ---------- paths / persistence (sync, run in worker threads) ----------


def staging_root() -> Path:
    root = Path(api_config.UPLOAD_STAGING_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _user_dir(user_key: str) -> Path:
    safe = USER_KEY_UNSAFE_RE.sub("_", str(user_key))
    if not safe:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    return staging_root() / safe


def _session_dir(user_key: str, session_id: str) -> Path:
    if not SESSION_ID_RE.match(session_id or ""):
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    return _user_dir(user_key) / session_id


def data_path(session: UploadSession) -> Path:
    return _session_dir(session.user_key, session.id) / DATA_NAME


@contextlib.contextmanager
def _locked(session_dir: Path) -> Iterator[None]:
    """Exclusive cross-process lock for one session (Granian = several worker processes)."""
    with (session_dir / LOCK_NAME).open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _load(session_dir: Path) -> UploadSession | None:
    try:
        raw = json.loads((session_dir / META_NAME).read_text())
        session = UploadSession(**raw)
    except (FileNotFoundError, NotADirectoryError, ValueError, TypeError):
        return None
    try:
        offset = (session_dir / DATA_NAME).stat().st_size
    except FileNotFoundError:
        offset = 0
    return replace(session, offset=offset)


def _write_meta(session_dir: Path, session: UploadSession) -> None:
    payload = asdict(session)
    payload.pop("offset")
    temp = session_dir / f"{META_NAME}.{uuid.uuid4().hex}.tmp"
    temp.write_text(json.dumps(payload))
    os.replace(temp, session_dir / META_NAME)


def _update(session_dir: Path, **fields: object) -> UploadSession | None:
    """Merge ``fields`` into the meta under the lock; None when the session is gone."""
    if not session_dir.is_dir():
        return None
    with _locked(session_dir):
        current = _load(session_dir)
        if current is None:
            return None
        updated = replace(current, **fields)
        _write_meta(session_dir, updated)
        return updated


def _discard_dir(session_dir: Path) -> None:
    shutil.rmtree(session_dir, ignore_errors=True)


def _iter_sessions(user_dir: Path) -> Iterator[tuple[Path, UploadSession | None]]:
    if not user_dir.is_dir():
        return
    for child in user_dir.iterdir():
        if child.is_dir():
            yield child, _load(child)


def _new_session_dir(user_key: str, session: UploadSession) -> None:
    session_dir = _session_dir(user_key, session.id)
    session_dir.mkdir(parents=True, mode=0o700)
    _write_meta(session_dir, session)


def _sweep_sync() -> int:
    now = time.time()
    removed = 0
    root = staging_root()
    for user_dir in root.iterdir():
        if not user_dir.is_dir():
            continue
        if user_dir.name == WORK_DIR_NAME:
            removed += _sweep_work_dir(user_dir, now)
            continue
        for session_dir, session in _iter_sessions(user_dir):
            # No readable meta = a crash mid-create: age by mtime instead of keeping it forever.
            expired = (
                session.expires_at < now
                if session is not None
                else session_dir.stat().st_mtime < now - SESSION_TTL_SECONDS
            )
            if expired:
                _discard_dir(session_dir)
                removed += 1
        with contextlib.suppress(OSError):
            user_dir.rmdir()  # only succeeds when empty
    return removed


def _sweep_work_dir(work_dir: Path, now: float) -> int:
    removed = 0
    for child in work_dir.iterdir():
        if child.stat().st_mtime < now - SESSION_TTL_SECONDS:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    return removed


def _check_quota(user_key: str, new_size_bytes: int) -> None:
    open_sessions = 0
    declared_bytes = 0
    for _, session in _iter_sessions(_user_dir(user_key)):
        if session is not None:
            open_sessions += 1
            declared_bytes += session.size_bytes
    if open_sessions >= MAX_OPEN_SESSIONS_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Você já tem {open_sessions} envios em andamento. "
                "Conclua ou cancele algum antes de enviar outro arquivo."
            ),
        )
    if declared_bytes + new_size_bytes > MAX_STAGED_BYTES_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=(
                "Limite de arquivos em envio atingido "
                f"({MAX_STAGED_BYTES_PER_USER // (1024 * BYTES_PER_MEGABYTE)} GB). "
                "Aguarde os envios atuais terminarem."
            ),
        )


def size_limit_for(mime_type: str) -> int:
    """Per-FILE cap: images are decoded in RAM so they stay small; the rest is only stored."""
    if (mime_type or "").lower().startswith("image/"):
        return api_config.IMAGE_MAX_BYTES
    return api_config.FILE_MAX_BYTES


def _create_sync(user_key: str, filename: str, mime_type: str, size_bytes: int) -> UploadSession:
    limit = size_limit_for(mime_type)
    if size_bytes > limit:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Arquivo muito grande ({math.ceil(size_bytes / BYTES_PER_MEGABYTE)} MB). "
                f"Máximo: {limit // BYTES_PER_MEGABYTE} MB."
            ),
        )
    _sweep_sync()
    _check_quota(user_key, size_bytes)
    now = time.time()
    session = UploadSession(
        id=uuid.uuid4().hex,
        user_key=str(user_key),
        filename=filename,
        mime_type=mime_type or "application/octet-stream",
        size_bytes=size_bytes,
        created_at=now,
        expires_at=now + SESSION_TTL_SECONDS,
    )
    _new_session_dir(user_key, session)
    return session


def _commit_chunk_sync(session_dir: Path, offset: int, part: Path, length: int) -> int:
    """Append a fully received chunk to ``data`` if (and only if) it continues the file."""
    if not session_dir.is_dir():
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    with _locked(session_dir):
        session = _load(session_dir)
        if session is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
        current = session.offset
        if session.phase != "open":
            raise HTTPException(status_code=409, detail="Este envio já foi concluído.")
        if offset + length <= current:
            return current  # retry of a chunk that already landed: idempotent
        if offset != current:
            raise OffsetMismatchError(current)
        if current + length > session.size_bytes:
            shutil.rmtree(session_dir, ignore_errors=True)
            raise HTTPException(
                status_code=400,
                detail="O arquivo enviado é maior do que o informado. Envie de novo.",
            )
        with part.open("rb") as source, (session_dir / DATA_NAME).open("ab") as target:
            shutil.copyfileobj(source, target, COPY_BUFFER_BYTES)
        _write_meta(session_dir, replace(session, expires_at=time.time() + SESSION_TTL_SECONDS))
        return current + length


def _store_prepared_sync(session_dir: Path, source: Path, mime: str, filename: str) -> None:
    if not session_dir.is_dir():  # the user cancelled while the conversion ran
        source.unlink(missing_ok=True)
        return
    with _locked(session_dir):
        target = session_dir / PREPARED_NAME
        try:
            os.replace(source, target)
        except OSError:  # different filesystem
            shutil.move(source, target)
        current = _load(session_dir)
        if current is not None:
            _write_meta(
                session_dir,
                replace(
                    current,
                    phase="ready",
                    error=None,
                    prepared_mime=mime,
                    prepared_filename=filename,
                ),
            )


# ---------- public async API ----------


async def create_session(
    user_key: str, filename: str, mime_type: str, size_bytes: int
) -> UploadSession:
    return await anyio.to_thread.run_sync(_create_sync, user_key, filename, mime_type, size_bytes)


async def get_session(user_key: str, session_id: str) -> UploadSession:
    """The session when it exists AND belongs to ``user_key``; 404 otherwise."""
    session = await anyio.to_thread.run_sync(_load, _session_dir(user_key, session_id))
    if session is None or session.expires_at < time.time():
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    return session


async def discard_session(user_key: str, session_id: str) -> None:
    await anyio.to_thread.run_sync(_discard_dir, _session_dir(user_key, session_id))


async def sweep_expired_sessions() -> int:
    """Delete expired sessions and stale work dirs. Called at startup and on every create."""
    removed = await anyio.to_thread.run_sync(_sweep_sync)
    if removed:
        log.info("upload_sessions_swept", removed=removed)
    return removed


async def append_chunk(
    user_key: str, session_id: str, offset: int, body: AsyncIterator[bytes]
) -> int:
    """Stream ``body`` to a part file, then append it atomically; returns the new offset.

    Raises ``OffsetMismatchError`` (router answers 409), ``HTTPException`` 400/404/413.
    """
    session_dir = _session_dir(user_key, session_id)
    session = await get_session(user_key, session_id)
    part = session_dir / f"part-{uuid.uuid4().hex}"
    received = 0
    try:
        async with await anyio.open_file(part, "wb") as out:
            async for piece in body:
                received += len(piece)
                if received > api_config.UPLOAD_CHUNK_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Pedaço grande demais "
                            f"(máximo {api_config.UPLOAD_CHUNK_BYTES // BYTES_PER_MEGABYTE} MB)."
                        ),
                    )
                await out.write(piece)
        if received == 0:
            raise HTTPException(status_code=400, detail="Pedaço vazio.")
        new_offset = await anyio.to_thread.run_sync(
            _commit_chunk_sync, session_dir, offset, part, received
        )
    finally:
        with contextlib.suppress(FileNotFoundError):
            part.unlink()
    log.debug("upload_chunk_committed", session=session.id, offset=new_offset)
    return new_offset


async def mark_processing(user_key: str, session_id: str) -> UploadSession:
    session_dir = _session_dir(user_key, session_id)
    updated = await anyio.to_thread.run_sync(
        lambda: _update(session_dir, phase="processing", error=None, processing_since=time.time())
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    return updated


async def mark_failed(user_key: str, session_id: str, error: str) -> None:
    session_dir = _session_dir(user_key, session_id)
    await anyio.to_thread.run_sync(lambda: _update(session_dir, phase="failed", error=error))


async def store_prepared(
    user_key: str, session_id: str, path: Path, mime_type: str, filename: str
) -> None:
    """Attach the converted artifact (moved into the session) and flip the state to ``ready``."""
    session_dir = _session_dir(user_key, session_id)
    await anyio.to_thread.run_sync(_store_prepared_sync, session_dir, path, mime_type, filename)


# ---------- consuming a staged file ----------


class StagedUploadFile(UploadFile):
    """An ``UploadFile`` backed by a file on disk. ``.path`` lets callers stream it (storage
    multipart upload, curl ``local_path``) instead of loading it into memory."""

    def __init__(self, path: Path, filename: str, content_type: str) -> None:
        self.path = path
        super().__init__(
            file=path.open("rb"),
            size=path.stat().st_size,
            filename=filename,
            headers=Headers({"content-type": content_type or "application/octet-stream"}),
        )


def open_staged_file(session: UploadSession) -> StagedUploadFile:
    """The prepared artifact when the session has one, otherwise the uploaded data."""
    session_dir = _session_dir(session.user_key, session.id)
    if session.phase == "ready":
        return StagedUploadFile(
            session_dir / PREPARED_NAME,
            session.prepared_filename or session.filename,
            session.prepared_mime or session.mime_type,
        )
    mime_type = session.mime_type or mimetypes.guess_type(session.filename)[0] or ""
    return StagedUploadFile(session_dir / DATA_NAME, session.filename, mime_type)


def _assert_consumable(session: UploadSession) -> None:
    state = session.state
    if state == "uploading":
        raise HTTPException(status_code=400, detail="O envio do arquivo ainda não terminou.")
    if state == "processing":
        raise HTTPException(status_code=409, detail="O arquivo ainda está sendo processado.")
    if state == "failed":
        raise HTTPException(
            status_code=400,
            detail=session.public_error or "O processamento do arquivo falhou. Envie de novo.",
        )


UserKeyDependency = Callable[[Request], Awaitable[str]]


def make_staged_or_direct_file(
    user_key_dependency: UserKeyDependency, *, required: bool = True
) -> Callable[..., AsyncIterator[UploadFile | None]]:
    """FastAPI dependency: the multipart ``file`` as-is, or the staged file of ``file_upload_id``.

    The session is discarded only when the endpoint finished without raising, so the client's
    retry after a failure reuses the already uploaded bytes. ``required=False`` yields ``None``
    when neither field came (routes where the file depends on another field, e.g. ``kind``).
    """

    async def resolve(
        request: Request,
        file: UploadFile | None = File(default=None),
        file_upload_id: str | None = Form(default=None),
    ) -> AsyncIterator[UploadFile | None]:
        if file is not None or not file_upload_id:
            if file is None and required:
                raise HTTPException(status_code=400, detail="Envie o arquivo.")
            yield file
            return
        user_key = await user_key_dependency(request)
        session = await get_session(user_key, file_upload_id)
        _assert_consumable(session)
        staged = open_staged_file(session)
        succeeded = False
        try:
            yield staged
            succeeded = True
        finally:
            await staged.close()
            if succeeded:
                await discard_session(user_key, session.id)

    return resolve


# ---------- router ----------


def _expires_iso(session: UploadSession) -> str:
    return datetime.fromtimestamp(session.expires_at, UTC).isoformat()


def build_upload_sessions_router(user_key_dependency: UserKeyDependency) -> APIRouter:
    """Router for ``/upload-sessions``; ``user_key_dependency`` authenticates and returns a str key."""
    router = APIRouter(prefix="/upload-sessions", tags=["upload-sessions"])

    @router.post("", status_code=201)
    async def create_upload_session(
        payload: CreateUploadSessionRequest, user_key: str = Depends(user_key_dependency)
    ) -> dict:
        session = await create_session(
            user_key, payload.filename, payload.mime_type, payload.size_bytes
        )
        return {
            "id": session.id,
            "chunk_bytes": api_config.UPLOAD_CHUNK_BYTES,
            "offset": session.offset,
            "expires_at": _expires_iso(session),
        }

    @router.put("/{session_id}")
    async def append_upload_chunk(
        session_id: str,
        request: Request,
        offset: int = Query(ge=0),
        user_key: str = Depends(user_key_dependency),
    ) -> Response:
        try:
            new_offset = await append_chunk(user_key, session_id, offset, request.stream())
        except OffsetMismatchError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "Posição do pedaço diferente da esperada. Retomando de onde parou.",
                    "offset": exc.offset,
                },
            )
        return JSONResponse({"offset": new_offset})

    @router.get("/{session_id}")
    async def read_upload_session(
        session_id: str, user_key: str = Depends(user_key_dependency)
    ) -> dict:
        session = await get_session(user_key, session_id)
        return {
            "id": session.id,
            "offset": session.offset,
            "size_bytes": session.size_bytes,
            "state": session.state,
            "error": session.public_error,
        }

    @router.delete("/{session_id}", status_code=204)
    async def delete_upload_session(
        session_id: str, user_key: str = Depends(user_key_dependency)
    ) -> Response:
        # 404 when the session is not this user's (or is gone): answering 204 told the caller
        # "deleted" while nothing happened (CRUD audit 2026-11-17, user decision). The frontend
        # never sends DELETE (`chunked-upload.ts` lets the sweeper expire abandoned sessions).
        await get_session(user_key, session_id)
        await discard_session(user_key, session_id)
        return Response(status_code=204)

    return router
