"""Persistent upload endpoint backing the chat composer.

Browser POSTs a multipart file → we validate against the selected agent's
``capabilities`` (image_input/audio_input/video_input), enforce per-kind size
limits and per-thread/per-user quotas, then persist the bytes via the central
``config.uploads`` module — canonical filename ``{slug}-{uuid4}.{ext}``, AVIF
for images, MIME whitelist for documents — and register a row in
``user_uploads`` (single source of truth, ``visibility='private'``).

Owner do path canônico = o ``user_id`` da sessão (``get_auth_context``). Não há
upload anônimo: todo arquivo tem dono e vira row em ``user_uploads``.
Layout final: ``users/{user_id}/chat/threads/{thread_id}/{slug}-{uuid4}.{ext}``.

A ``StaticFiles`` mount em ``main.py`` expõe o diretório sob
``UPLOADS_HTTP_PREFIX`` para a URL retornada ser cacheável pelo browser.

See rule ``uploads.md`` and skill ``uploads-storage``.
"""

import hashlib
import mimetypes
import os
from pathlib import Path
from typing import Any

from asyncpg.connection import Connection
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from api.core.exceptions import BadRequestError
from api.models.uploads.upload_jsonb import UploadKind, UploadVisibility
from api.models.uploads.user_upload import UserUpload
from api.repositories.uploads.user_upload_repository import user_upload_repository
from api.services.agents.registry import get_agents_registry
from api.services.auth import get_auth_context
from config.api import api_config
from config.database import get_conn
from config.uploads import (
    DEFAULT_DOCUMENT_MIME_WHITELIST,
    USERS,
    save_upload,
    slugify,
)

router = APIRouter()

# Path segments para o layout canônico do chat.
CHAT_DOMAIN = "chat"
CHAT_THREADS_SUB = "threads"
ENTITY_CHAT_SESSION = "chat_session"

# Document mime patterns (everything else with these prefixes counts as "doc"
# for per-thread quota purposes).
DOC_MIME_PREFIXES = ("application/", "text/")

# Mime prefixes that are not "documents" (those go through MarkItDown without a
# capability gate). Keep in sync with ``ChatComposer.buildAcceptAttribute``.
GATED_MIME_PREFIXES: tuple[tuple[str, str], ...] = (
    ("image/", "image_input"),
    ("audio/", "audio_input"),
    ("video/", "video_input"),
)


def _capability_key_for(media_type: str) -> str | None:
    for prefix, capability in GATED_MIME_PREFIXES:
        if media_type.startswith(prefix):
            return capability
    return None


def _max_bytes_for(media_type: str) -> int:
    if media_type.startswith("image/"):
        return api_config.IMAGE_MAX_BYTES
    return api_config.DOCUMENT_MAX_BYTES


def _safe_segment(value: str | None) -> str | None:
    """Sanitize a single path component sent by the client."""
    if not value:
        return None
    cleaned = Path(value).name
    if not cleaned or cleaned in ("..", "."):
        return None
    return cleaned


def _thread_dir_for(user_id: str, thread_id: str) -> Path:
    """Canonical thread directory under UPLOADS_DIR."""
    return api_config.UPLOADS_DIR / USERS / user_id / CHAT_DOMAIN / CHAT_THREADS_SUB / thread_id


def _is_image(media_type: str) -> bool:
    return media_type.startswith("image/")


def _is_document(media_type: str) -> bool:
    return any(media_type.startswith(p) for p in DOC_MIME_PREFIXES) and not _is_image(media_type)


def _count_thread_files(thread_dir: Path) -> tuple[int, int, int]:
    """Return (total, images, documents) currently present in a thread's dir."""
    if not thread_dir.is_dir():
        return 0, 0, 0
    total = images = docs = 0
    for entry in os.scandir(thread_dir):
        if not entry.is_file():
            continue
        total += 1
        ext = Path(entry.name).suffix.lower()
        guessed, _ = mimetypes.guess_type(entry.name)
        media_type = (guessed or "").lower()
        if _is_image(media_type) or ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"}:
            images += 1
        else:
            docs += 1
    return total, images, docs


def _user_usage(user_dir: Path) -> tuple[int, int]:
    """Return (file_count, total_bytes) for a user across all subtrees."""
    if not user_dir.is_dir():
        return 0, 0
    count = 0
    size = 0
    for root, _dirs, files in os.walk(user_dir):
        for name in files:
            try:
                stat = (Path(root) / name).stat()
            except OSError:
                continue
            count += 1
            size += stat.st_size
    return count, size


def _quota_error(code: str, **extra: Any) -> HTTPException:
    detail = {"code": code, **extra}
    return HTTPException(status_code=413, detail=detail)


def _enforce_quotas(
    safe_user: str,
    safe_thread: str | None,
    media_type: str,
    incoming_size: int,
    existing_dedup_hit: bool,
) -> None:
    """Raise 413 if any per-thread or per-user quota would be exceeded.

    ``existing_dedup_hit`` = True quando já existe arquivo com o mesmo SHA256
    na thread — re-anexar o mesmo arquivo é grátis em quota.
    """
    if existing_dedup_hit:
        return
    if not safe_thread:
        return  # sem thread não há contagem por-thread; o user já vem da sessão

    user_dir = api_config.UPLOADS_DIR / USERS / safe_user
    thread_dir = _thread_dir_for(safe_user, safe_thread)

    total, images, docs = _count_thread_files(thread_dir)

    if total + 1 > api_config.THREAD_MAX_FILES_TOTAL:
        raise _quota_error(
            "thread_files_full",
            limit=api_config.THREAD_MAX_FILES_TOTAL,
            current=total,
        )
    if _is_image(media_type) and images + 1 > api_config.THREAD_MAX_IMAGES:
        raise _quota_error(
            "thread_images_full",
            limit=api_config.THREAD_MAX_IMAGES,
            current=images,
        )
    if _is_document(media_type) and docs + 1 > api_config.THREAD_MAX_DOCUMENTS:
        raise _quota_error(
            "thread_documents_full",
            limit=api_config.THREAD_MAX_DOCUMENTS,
            current=docs,
        )

    user_count, user_bytes = _user_usage(user_dir)
    if user_count + 1 > api_config.USER_MAX_FILES_TOTAL:
        raise _quota_error(
            "user_files_full",
            limit=api_config.USER_MAX_FILES_TOTAL,
            current=user_count,
        )
    if user_bytes + incoming_size > api_config.USER_MAX_BYTES_TOTAL:
        raise _quota_error(
            "user_storage_full",
            limit=api_config.USER_MAX_BYTES_TOTAL,
            current=user_bytes,
            incoming=incoming_size,
        )


def _content_dedup_slug(digest: str) -> str:
    """Slug = SHA256 hex; manter compatível com o slugify (alfanumérico)."""
    return slugify(digest)


def _find_dedup_match(thread_dir: Path, digest: str) -> Path | None:
    """SHA256 prefix dedup: filename canônico é ``{slug}-{uuid4}.{ext}``,
    então buscamos arquivos cujo slug seja o digest.

    O slug salvo é ``slugify(digest)`` (que trunca em SLUG_MAX_LENGTH), então a
    busca de prefixo precisa usar o MESMO valor — não o digest cru, senão nunca
    casa (SHA256 hex tem 64 chars, slug máx 60).

    Custo aceitável: ``scandir`` simples na pasta da thread (≤10 arquivos por quota).
    """
    if not thread_dir.is_dir():
        return None
    prefix = f"{_content_dedup_slug(digest)}-"
    for entry in os.scandir(thread_dir):
        if entry.is_file() and entry.name.startswith(prefix):
            return Path(entry.path)
    return None


@router.post("")
async def create_upload(
    file: UploadFile = File(...),
    model_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    ctx: dict = Depends(get_auth_context),
    agents_registry: dict = Depends(get_agents_registry),
    conn: Connection = Depends(get_conn),
) -> dict[str, Any]:
    """Persist a single attachment and return the URL the chat should reference."""
    media_type = (file.content_type or "application/octet-stream").lower()
    raw_filename = file.filename or "file"

    # Capability gate — only when the caller tells us which agent it's targeting.
    capability = _capability_key_for(media_type)
    if model_id and capability:
        agent_info = agents_registry.get(model_id)
        if agent_info is None:
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
        caps = agent_info.get("capabilities") or {}
        if not caps.get(capability):
            raise HTTPException(
                status_code=415,
                detail={
                    "code": f"{capability.split('_')[0]}_not_supported",
                    "model_id": model_id,
                    "media_type": media_type,
                    "filename": raw_filename,
                },
            )

    payload = await file.read()
    size = len(payload)
    if size == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    max_bytes = _max_bytes_for(media_type)
    if size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "too_large",
                "max_bytes": max_bytes,
                "size": size,
                "filename": raw_filename,
            },
        )

    # MIME validation antecipada para documentos (whitelist do módulo central).
    if _is_document(media_type):
        bare = media_type.split(";")[0].strip()
        if bare not in DEFAULT_DOCUMENT_MIME_WHITELIST:
            raise HTTPException(
                status_code=415,
                detail={
                    "code": "unsupported_type",
                    "media_type": media_type,
                    "filename": raw_filename,
                },
            )

    # Reset cursor — save_upload faz ``await file.read()`` de novo abaixo.
    await file.seek(0)

    # Owner sempre vem da sessão — nunca de um param do cliente.
    owner_user_id: str = ctx["user_id"]
    safe_user = str(owner_user_id)
    safe_thread = _safe_segment(session_id)

    # Dedup via SHA256: se já existe na thread, retorna a URL existente sem rewrite.
    digest = hashlib.sha256(payload).hexdigest()
    dedup_hit: Path | None = None
    if safe_thread:
        thread_dir = _thread_dir_for(safe_user, safe_thread)
        dedup_hit = _find_dedup_match(thread_dir, digest)

    _enforce_quotas(
        safe_user,
        safe_thread,
        media_type,
        size,
        existing_dedup_hit=dedup_hit is not None,
    )

    if dedup_hit is not None:
        # Reuse existing file — não regrava bytes nem cria nova row.
        url = (
            f"{api_config.UPLOADS_HTTP_PREFIX}/{USERS}/{safe_user}/{CHAT_DOMAIN}/"
            f"{CHAT_THREADS_SUB}/{safe_thread}/{dedup_hit.name}"
        )
        return {
            "url": url,
            "filename": raw_filename,
            "media_type": media_type,
            "size": size,
        }

    # Salva via módulo central — slug = digest sha256 (mantém dedup deterministico).
    mode: str
    if _is_image(media_type):
        mode = "image"
    elif _is_document(media_type):
        mode = "document"
    else:
        mode = "raw"

    if safe_thread:
        path_parts: tuple[str, ...] = (
            USERS,
            safe_user,
            CHAT_DOMAIN,
            CHAT_THREADS_SUB,
            safe_thread,
        )
    else:
        path_parts = (USERS, safe_user, CHAT_DOMAIN)

    try:
        result = await save_upload(
            file,
            *path_parts,
            base_name=_content_dedup_slug(digest),
            mode=mode,  # type: ignore[arg-type]
        )
    except BadRequestError as exc:
        message = str(exc.detail)
        if "suportado" in message:
            status_code, code = 415, "unsupported_type"
        elif "limite" in message:
            status_code, code = 413, "too_large"
        else:
            # Corrupt/undecodable image or AVIF encode failure — bad request.
            status_code, code = 400, "invalid_file"
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": code,
                "media_type": media_type,
                "filename": raw_filename,
                "message": message,
            },
        ) from exc

    # Todo upload de chat tem dono (sessão) — sempre rastreado em user_uploads.
    record = UserUpload(
        owner_user_id=owner_user_id,
        entity_type=ENTITY_CHAT_SESSION,
        entity_id=safe_thread,
        kind=UploadKind.ATTACHMENT,
        url=result.url,
        filename=raw_filename,
        mime_type=result.mime_type,
        size_bytes=result.size_bytes,
        width=result.width,
        height=result.height,
        visibility=UploadVisibility.PRIVATE,
    )
    await user_upload_repository.create(conn, record)

    return {
        "url": result.url,
        "filename": raw_filename,
        "media_type": "image/avif" if mode == "image" else media_type,
        "size": size,
    }
