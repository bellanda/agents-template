"""Resolve a chat attachment URL to an on-disk file the caller is allowed to read.

Canonical copy (audit 2026-11-13 skills-backend-01 / core-ai-02; ported from optimuslar). Two
layers, both mandatory, and identity/path NEVER comes from the request body:

  containment - the file must resolve inside UPLOADS_DIR (``..`` and symlinks neutralised).
  ownership   - containment alone is not enough: another user's private attachment also lives
  inside UPLOADS_DIR, so feeding it to the LLM would be cross-user exfiltration. The file must
  match a ``user_uploads`` row that is public or owned by the caller; untracked-but-contained
  files are dropped (every legitimate upload has a row, see routes/uploads.py).

There is deliberately NO "raw server path" entry point: the legacy ``ChatRequest.files`` channel
(arbitrary paths sent by the client, read by the server) was removed. Attachments arrive as
``parts`` of the user message and reference ``/uploads/...`` URLs only.
"""

from pathlib import Path
from urllib.parse import urlparse

from asyncpg.connection import Connection

from api.core.logging import get_logger
from api.models.uploads.upload_jsonb import UploadVisibility
from api.repositories.uploads.user_upload_repository import user_upload_repository
from config.api import api_config

log = get_logger(__name__)


def _contained(candidate: Path) -> Path | None:
    """``resolve()`` + ``relative_to()`` neutralise ``..`` and symlink escapes."""
    base = api_config.UPLOADS_DIR.resolve()
    try:
        target = candidate.resolve()
        target.relative_to(base)
    except (ValueError, OSError):
        return None
    return target if target.is_file() else None


def resolve_upload_path(url: str) -> Path | None:
    """If ``url`` points at our /uploads mount, return the contained on-disk Path; else None.

    Accepts the flat legacy layout (``/uploads/<hash>.ext``) and the scoped one
    (``/uploads/users/<user_id>/chat/threads/<thread_id>/<hash>.ext``). Each segment is
    sanitised and the final path must stay inside ``UPLOADS_DIR``.
    """
    if not url:
        return None
    parsed = urlparse(url)
    path = parsed.path or url
    prefix = api_config.UPLOADS_HTTP_PREFIX
    if not path.startswith(prefix + "/"):
        return None
    raw_relative = path[len(prefix) + 1 :]
    safe_segments: list[str] = []
    for segment in raw_relative.split("/"):
        if not segment:
            continue
        cleaned = Path(segment).name
        if not cleaned or cleaned in ("..", "."):
            return None
        safe_segments.append(cleaned)
    if not safe_segments:
        return None
    return _contained(api_config.UPLOADS_DIR.joinpath(*safe_segments))


def _upload_url_for(candidate: Path) -> str | None:
    base = api_config.UPLOADS_DIR.resolve()
    try:
        relative = candidate.resolve().relative_to(base)
    except ValueError:
        return None
    return f"{api_config.UPLOADS_HTTP_PREFIX}/{relative.as_posix()}"


async def authorize_upload_path(
    candidate: Path | None,
    conn: Connection,
    owner_user_id: str,
    is_superuser: bool = False,
) -> Path | None:
    """Keep a contained upload only if the caller may read it: public, own, or superuser."""
    if candidate is None:
        return None
    url = _upload_url_for(candidate)
    if url is None:
        return None
    record = await user_upload_repository.find_by_url(conn, url)
    if record is None:
        log.warning("chat_upload_untracked_dropped", url=url)
        return None
    if record["visibility"] == UploadVisibility.PUBLIC.value:
        return candidate
    if is_superuser or record["owner_user_id"] == owner_user_id:
        return candidate
    log.warning(
        "chat_upload_ownership_denied",
        url=url,
        record_owner=record["owner_user_id"],
        caller=owner_user_id,
    )
    return None


async def resolve_authorized_upload(
    conn: Connection, url: str, owner_user_id: str, is_superuser: bool = False
) -> Path | None:
    """URL -> contained path -> ownership check, in one call (what the chat route needs)."""
    return await authorize_upload_path(resolve_upload_path(url), conn, owner_user_id, is_superuser)
