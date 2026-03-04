import tomllib

from dotenv import load_dotenv

from config import paths
from config.tools import getenv_or_raise_exception

load_dotenv(override=True)

with open(paths.BASE_DIR / "pyproject.toml", "rb") as f:
    pyproject_data = tomllib.load(f)


class APIConfig:
    """Core Server Configuration: Network, Metadata and Uploads"""

    # ----------------------------------------------------------------------------
    # 📦 CORE APPLICATION SETTINGS
    # ----------------------------------------------------------------------------
    PROJECT_NAME = pyproject_data["project"]["name"]
    PROJECT_DESCRIPTION = pyproject_data["project"]["description"]
    PROJECT_VERSION = pyproject_data["project"]["version"]

    # ----------------------------------------------------------------------------
    # 🌐 SERVER CONFIGURATION
    # ----------------------------------------------------------------------------
    HOST: str = getenv_or_raise_exception("HOST")
    PORT: int = int(getenv_or_raise_exception("PORT"))
    API_V1_PREFIX = "/api/v1"

    # Granian specific
    GRANIAN_INTERFACE: str = getenv_or_raise_exception("GRANIAN_INTERFACE")
    GRANIAN_HTTP: str = getenv_or_raise_exception("GRANIAN_HTTP")
    GRANIAN_LOOP: str = getenv_or_raise_exception("GRANIAN_LOOP")
    GRANIAN_WORKERS: int = int(getenv_or_raise_exception("GRANIAN_WORKERS"))

    # ----------------------------------------------------------------------------
    # 📁 UPLOAD PATHS & SIZE LIMITS
    # ----------------------------------------------------------------------------
    UPLOADS_DIR = paths.BASE_DIR / "uploads"
    UPLOADS_HTTP_PREFIX: str = f"{API_V1_PREFIX}/uploads"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB
    DOCUMENT_MAX_BYTES: int = 20 * 1024 * 1024  # 20 MB


api_config = APIConfig()
