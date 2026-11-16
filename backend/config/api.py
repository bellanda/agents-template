import os
import tomllib
from pathlib import Path

from config import paths

with open(paths.BASE_DIR / "pyproject.toml", "rb") as f:
    pyproject_data = tomllib.load(f)


class APIConfig:
    """Core server configuration: metadata, API prefix, upload paths and limits"""

    # ----------------------------------------------------------------------------
    # 📦 CORE APPLICATION SETTINGS
    # ----------------------------------------------------------------------------
    PROJECT_NAME = pyproject_data["project"]["name"]
    PROJECT_DESCRIPTION = pyproject_data["project"]["description"]
    PROJECT_VERSION = pyproject_data["project"]["version"]

    # Network bind (host/port/workers) is NOT here: Granian takes GRANIAN_* from the compose
    # `environment:` (config/docker/compose.<env>.yaml) and uvicorn's dev entrypoint in main.py
    # binds 0.0.0.0:8000.
    API_V1_PREFIX = "/api/v1"

    # ----------------------------------------------------------------------------
    # 📁 UPLOAD PATHS, SIZE LIMITS & QUOTAS
    # ----------------------------------------------------------------------------
    UPLOADS_DIR = paths.BASE_DIR / "uploads"
    UPLOADS_HTTP_PREFIX: str = f"{API_V1_PREFIX}/uploads"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # Per-FILE limits (decision 2026-11-16). nginx caps each REQUEST at 20 MB and Cloudflare at
    # 100 MB / ~100 s, so a file above UPLOAD_CHUNK_BYTES travels in chunks through
    # `/api/v1/upload-sessions` (services/uploads/upload_sessions.py); the limit per FILE lives here.
    # Images are decoded in RAM (50 MP budget) so they stay small; anything that is only STORED
    # (video, PDF, zip...) may be big because it is streamed to disk, never held in memory.
    IMAGE_MAX_BYTES: int = 20 * 1024 * 1024  # 20 MB
    FILE_MAX_BYTES: int = 500 * 1024 * 1024  # 500 MB
    DOCUMENT_MAX_BYTES: int = FILE_MAX_BYTES
    UPLOAD_CHUNK_BYTES: int = 8 * 1024 * 1024  # 8 MiB per PUT; must stay well under nginx's 20M
    # Chunk staging area. NOT /tmp (64 MB tmpfs) and NOT UPLOADS_DIR (bind mount, root-owned on
    # some hosts): in Docker it is the named volume `upload-staging`.
    UPLOAD_STAGING_DIR: Path = Path(
        os.getenv("UPLOAD_STAGING_DIR", str(paths.BASE_DIR / "upload-staging"))
    )
    UPLOAD_STAGING_DIR.mkdir(parents=True, exist_ok=True)
    # What the AI is willing to READ (MarkItDown / base64 inline in the prompt). A big PDF may be
    # stored (FILE_MAX_BYTES) but is never loaded whole into RAM for the model.
    AI_ATTACHMENT_MAX_BYTES: int = 20 * 1024 * 1024  # 20 MB

    # Per-thread caps. Counts files currently present in the thread directory —
    # idempotent uploads (same sha256) don't bump the counter.
    THREAD_MAX_IMAGES: int = 6
    THREAD_MAX_DOCUMENTS: int = 8
    THREAD_MAX_FILES_TOTAL: int = 10

    # Per-user caps (across all threads).
    USER_MAX_FILES_TOTAL: int = 200
    USER_MAX_BYTES_TOTAL: int = 500 * 1024 * 1024  # 500 MB


api_config = APIConfig()
