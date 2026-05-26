"""Canonical upload pipeline.

Saves UploadFile or raw bytes to disk under UPLOADS_DIR; returns
UploadResult(url, filename, mime_type, size_bytes, width, height) for the
caller to persist in the ``org_uploads`` / ``user_uploads`` table.

Three modes: raw, image (AVIF + profile resize), document (MIME-whitelisted,
ext-preserving). Filename is always canonical: ``{slug}-{uuid4}.{ext}``.

Ownership-prefixed paths: ``orgs/{org_id}/`` via ``org_dir()`` for
organization-owned uploads, ``users/{user_id}/`` via ``user_dir()`` for
user-owned uploads. Each project persists into ``org_uploads`` / ``user_uploads``
accordingly. This template is user-owned (chat attachments) → ``user_uploads``.

See rule ``uploads.md`` and skill ``uploads-storage`` for invariants and
patterns. Do not bypass ``save_upload``.
"""

from __future__ import annotations

import base64
import mimetypes
import re
import shutil
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import anyio
import cv2
import numpy as np
from fastapi import UploadFile

from api.core.exceptions import BadRequestError
from config.api import api_config

# ---------- constants ----------

SLUG_MAX_LENGTH = 60
AVIF_QUALITY = 80

ImageProfile = Literal["original", "hd", "full_hd"]
PROFILE_LONGEST_SIDE: dict[str, int] = {"hd": 1280, "full_hd": 1920}

ALLOWED_IMAGE_EXTENSIONS = frozenset(
    {".bmp", ".jpeg", ".jpg", ".png", ".webp", ".tiff", ".tif", ".avif"}
)

# Extensions Python's stdlib `mimetypes` does not map out of the box.
MIME_EXT_OVERRIDES: dict[str, str] = {
    "application/x-yaml": ".yaml",
    "application/yaml": ".yaml",
    "text/yaml": ".yaml",
    "text/x-yaml": ".yaml",
    "text/markdown": ".md",
    "text/x-markdown": ".md",
    "audio/webm": ".webm",
    "video/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "application/gpx+xml": ".gpx",
}

DEFAULT_DOCUMENT_MIME_WHITELIST: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
        "text/markdown",
        "application/json",
        "application/rtf",
    }
)

# Path segment constants. Pass into save_upload / dir_path / url_path positionally.
# Layout: ``uploads/orgs/{org_id}/{domain}/{entity_id}/...``
#         ``uploads/users/{user_id}/{domain}/{entity_id}/...``
ORGS = "orgs"
USERS = "users"
AVATARS = "avatars"
CHAT = "chat"
EXPORTS = "exports"
DOCUMENTS = "documents"
GALLERY = "gallery"
MEDIA = "media"

DATA_URL_RE = re.compile(r"^data:image/[^;]+;base64,(.+)$", re.IGNORECASE)

# ---------- types ----------


@dataclass
class UploadResult:
    """Result of save_upload. Persist into ``org_uploads`` / ``user_uploads``."""

    url: str
    filename: str
    mime_type: str | None
    size_bytes: int
    width: int | None = None
    height: int | None = None


# ---------- tenancy ----------


def org_dir(org_id: object) -> tuple[str, str]:
    """Return the ``("orgs", str(org_id))`` prefix for organization-owned paths.

    Star-unpack at the call site::

        save_upload(file, *org_dir(org_id), VEHICLES, vehicle_id, PHOTOS, ...)
        delete_directory(*org_dir(org_id), ASSESSMENTS, assessment_id)
    """
    return (ORGS, str(org_id))


def user_dir(user_id: object) -> tuple[str, str]:
    """Return the ``("users", str(user_id))`` prefix for user-owned paths.

    Star-unpack at the call site::

        save_upload(file, *user_dir(user_id), AVATARS, fixed_name="avatar", ...)
    """
    return (USERS, str(user_id))


# ---------- path / url helpers ----------


# Storage = filesystem local hoje (NVMe). A migração para object storage
# (B2BackBlazeStorage / S3 / Azure / GCS) entra atrás de um StorageBackend
# Protocol — ver skill `uploads-storage`. Será feito na sequência.
# TODO(b2): extrair save_bytes/delete_file/delete_tree/build_url para StorageBackend
#           + B2BackBlazeStorage() selecionado por settings.storage.backend.
def get_upload_base() -> Path:
    return Path(api_config.UPLOADS_DIR)


def dir_path(*parts: str | int) -> Path:
    """Build filesystem path under UPLOADS_DIR."""
    return get_upload_base() / Path(*map(str, parts))


def url_path(*parts: str | int) -> str:
    """Build HTTP URL path (e.g. /api/v1/uploads/orgs/<id>/...)."""
    return f"{api_config.UPLOADS_HTTP_PREFIX}/{'/'.join(map(str, parts))}"


def url_to_filesystem_path(url: str) -> Path | None:
    """Convert a stored URL back to its filesystem path. Returns None when
    the URL doesn't belong to the uploads tree."""
    if not url:
        return None
    prefix = api_config.UPLOADS_HTTP_PREFIX
    if url.startswith(prefix + "/"):
        relative = url.removeprefix(prefix + "/").lstrip("/").replace("..", "")
    elif url.startswith("/uploads/"):
        relative = url.removeprefix("/uploads/").lstrip("/").replace("..", "")
    else:
        return None
    if not relative:
        return None
    return get_upload_base() / relative


# ---------- filename helpers ----------


def safe_filename(original: str) -> str:
    """Replace unsafe chars with `_`; keep word chars, hyphen, underscore, dot."""
    return re.sub(r"[^\w\-_.]", "_", original).strip("_") or "file"


def slugify(value: str) -> str:
    """Slug for filenames: lowercase ASCII, spaces→hyphen, max SLUG_MAX_LENGTH.

    Strips diacritics via NFKD, collapses any run of non-[a-z0-9] into a single
    ``-``, trims leading/trailing hyphens. Empty → ``"file"``.
    """
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    if not slug:
        return "file"
    return slug[:SLUG_MAX_LENGTH].rstrip("-") or "file"


def ext_from_name(original_name: str, mime_type: str | None = None) -> str:
    """Resolve extension: filename suffix first, then mime, then ``.bin``."""
    name = (original_name or "file").strip() or "file"
    suffix = Path(name).suffix.lower()
    if suffix:
        return suffix
    if mime_type:
        bare = mime_type.split(";")[0].strip().lower()
        override = MIME_EXT_OVERRIDES.get(bare)
        if override:
            return override
        guessed = mimetypes.guess_extension(bare)
        if guessed:
            return guessed.lower()
    return ".bin"


def generate_upload_filename(base_name: str, ext: str) -> str:
    """Canonical filename: ``{slug}-{uuid4}{ext}``.

    Slug ASCII-safe lowercase capped at SLUG_MAX_LENGTH. UUID canonical
    hyphenated. Slug + UUID joined by a single hyphen.
    """
    slug = slugify(base_name)
    file_key = str(uuid.uuid4())
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return f"{slug}-{file_key}{ext}"


# ---------- delete helpers ----------


async def delete_file_by_url(url: str) -> bool:
    """Delete a file from disk by its stored URL. Returns True if deleted."""
    fs_path = url_to_filesystem_path(url)
    if not fs_path or not fs_path.exists():
        return False
    await anyio.to_thread.run_sync(fs_path.unlink)
    return True


async def delete_directory(*parts: str | int) -> bool:
    """Delete an entire uploads sub-tree. Returns True if anything was removed."""
    path = dir_path(*parts)
    if not path.exists():
        return False
    await anyio.to_thread.run_sync(shutil.rmtree, path)
    return True


# ---------- image pipeline ----------


def decode_image_bytes(content: bytes) -> np.ndarray:
    """OpenCV decode bytes → ndarray. Raises BadRequestError on invalid bytes."""
    arr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise BadRequestError(detail="Imagem inválida ou corrompida.")
    return img


def decode_data_url_image(data_url: str) -> np.ndarray:
    """Decode ``data:image/...;base64,...`` to ndarray."""
    match = DATA_URL_RE.match(data_url.strip())
    if not match:
        raise BadRequestError(detail="Data URL inválida.")
    return decode_image_bytes(base64.b64decode(match.group(1)))


def fit_inside(img: np.ndarray, longest_side: int) -> np.ndarray:
    """Resize so the longest side equals ``longest_side``, preserving aspect
    ratio. Never upscales."""
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= longest_side:
        return img
    scale = longest_side / longest
    new_w = max(1, round(w * scale))
    new_h = max(1, round(h * scale))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def encode_avif_bytes(img: np.ndarray, quality: int = AVIF_QUALITY) -> bytes:
    """Encode ndarray as AVIF bytes."""
    ok, buf = cv2.imencode(".avif", img, [cv2.IMWRITE_AVIF_QUALITY, quality])
    if not ok or buf is None:
        raise BadRequestError(detail="Falha ao codificar imagem em AVIF.")
    return buf.tobytes()


def process_image_sync(
    content: bytes,
    profile: ImageProfile,
    max_bytes: int,
) -> tuple[bytes, int, int]:
    """bytes → ndarray → optional fit_inside by profile → AVIF bytes.

    Returns (avif_bytes, width, height). Raises BadRequestError when bytes
    exceed ``max_bytes`` or decoding/encoding fail.
    """
    if len(content) > max_bytes:
        raise BadRequestError(
            detail=f"Imagem maior que o limite ({max_bytes // (1024 * 1024)} MB)."
        )
    img = decode_image_bytes(content)
    if profile != "original":
        img = fit_inside(img, PROFILE_LONGEST_SIDE[profile])
    out = encode_avif_bytes(img)
    h, w = img.shape[:2]
    return out, w, h


# ---------- MIME validation ----------


def validate_document_mime(
    file: UploadFile,
    allowed: set[str] | frozenset[str],
) -> None:
    """Reject the upload when ``file.content_type`` is not in ``allowed``."""
    bare = (file.content_type or "").split(";", 1)[0].strip().lower()
    if bare not in {m.lower() for m in allowed}:
        raise BadRequestError(
            detail=(f"Tipo não suportado: {file.content_type}. Permitidos: {sorted(allowed)}")
        )


# ---------- public API ----------


async def save_upload(
    file: UploadFile,
    *path_parts: str | int,
    fixed_name: str | None = None,
    base_name: str | None = None,
    ext: str | None = None,
    mode: Literal["raw", "image", "document"] = "raw",
    image_profile: ImageProfile = "full_hd",
    max_bytes: int | None = None,
    allowed_mime: set[str] | frozenset[str] | None = None,
) -> UploadResult:
    """Save an ``UploadFile`` under UPLOADS_DIR.

    Returns ``UploadResult(url, filename, mime_type, size_bytes, width, height)``.
    Caller is responsible for creating the ``org_uploads`` / ``user_uploads`` row.

    Modes
    -----
    raw      : bytes as-is. Ext from filename. Optional ``max_bytes``.
    image    : decode → optional resize per ``image_profile`` → AVIF.
               Ext forced to ``.avif``. ``max_bytes`` defaults to
               ``api_config.IMAGE_MAX_BYTES``.
    document : bytes as-is, original ext preserved (or ``ext`` override).
               ``allowed_mime`` defaults to ``DEFAULT_DOCUMENT_MIME_WHITELIST``.
               ``max_bytes`` defaults to ``api_config.DOCUMENT_MAX_BYTES``.

    Filename is always canonical: ``{slug}-{uuid4}.{ext}``.
    """
    base = dir_path(*path_parts)
    await anyio.to_thread.run_sync(lambda: base.mkdir(parents=True, exist_ok=True))

    if mode == "document":
        whitelist = allowed_mime if allowed_mime is not None else DEFAULT_DOCUMENT_MIME_WHITELIST
        validate_document_mime(file, whitelist)

    content = await file.read()
    raw_size = len(content)
    width: int | None = None
    height: int | None = None
    mime_type: str | None = file.content_type or None

    if mode == "image":
        limit = max_bytes or api_config.IMAGE_MAX_BYTES
        content, width, height = await anyio.to_thread.run_sync(
            process_image_sync, content, image_profile, limit
        )
        target_ext = ".avif"
        mime_type = "image/avif"
    else:
        target_ext = ext or ext_from_name(file.filename or "", file.content_type)
        if target_ext and not target_ext.startswith("."):
            target_ext = f".{target_ext}"
        if mode == "document":
            limit = max_bytes or api_config.DOCUMENT_MAX_BYTES
            if raw_size > limit:
                raise BadRequestError(
                    detail=f"Arquivo maior que o limite ({limit // (1024 * 1024)} MB)."
                )
        elif max_bytes is not None and raw_size > max_bytes:
            raise BadRequestError(
                detail=f"Arquivo maior que o limite ({max_bytes // (1024 * 1024)} MB)."
            )

    name_source = fixed_name or base_name or file.filename or "file"
    stem = Path(safe_filename(name_source)).stem
    fname = generate_upload_filename(stem, target_ext)
    fp = base / fname
    await anyio.Path(fp).write_bytes(content)

    return UploadResult(
        url=url_path(*path_parts, fname),
        filename=fname,
        mime_type=mime_type,
        size_bytes=len(content),
        width=width,
        height=height,
    )


async def save_image_bytes(
    avif_bytes: bytes,
    *path_parts: str | int,
    base_name: str,
    width: int | None = None,
    height: int | None = None,
) -> UploadResult:
    """Write already-encoded AVIF bytes under UPLOADS_DIR.

    Use after ``process_image_sync`` or any pre-encoded AVIF source. Filename
    is canonical ``{slug}-{uuid4}.avif``.
    """
    base = dir_path(*path_parts)
    await anyio.to_thread.run_sync(lambda: base.mkdir(parents=True, exist_ok=True))
    stem = Path(safe_filename(base_name)).stem
    fname = generate_upload_filename(stem, ".avif")
    fp = base / fname
    await anyio.Path(fp).write_bytes(avif_bytes)
    return UploadResult(
        url=url_path(*path_parts, fname),
        filename=fname,
        mime_type="image/avif",
        size_bytes=len(avif_bytes),
        width=width,
        height=height,
    )


__all__ = [
    "ALLOWED_IMAGE_EXTENSIONS",
    "AVATARS",
    "AVIF_QUALITY",
    "CHAT",
    "DEFAULT_DOCUMENT_MIME_WHITELIST",
    "DOCUMENTS",
    "EXPORTS",
    "GALLERY",
    "MEDIA",
    "MIME_EXT_OVERRIDES",
    "ORGS",
    "PROFILE_LONGEST_SIDE",
    "SLUG_MAX_LENGTH",
    "USERS",
    "ImageProfile",
    "UploadResult",
    "decode_data_url_image",
    "decode_image_bytes",
    "delete_directory",
    "delete_file_by_url",
    "dir_path",
    "encode_avif_bytes",
    "ext_from_name",
    "fit_inside",
    "generate_upload_filename",
    "get_upload_base",
    "org_dir",
    "process_image_sync",
    "safe_filename",
    "save_image_bytes",
    "save_upload",
    "slugify",
    "url_path",
    "url_to_filesystem_path",
    "user_dir",
    "validate_document_mime",
]
