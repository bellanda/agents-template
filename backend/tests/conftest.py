import os
from pathlib import Path

# Settings load at import time (config/settings.py), so the hermetic test yaml and the required
# secrets must be in env BEFORE any `api.*` import. Without this, collecting any test that imports
# the app fails with "DATABASE_URL is not set at .env" (2026-10-13). Port 5433 = backend/tests/compose.yml.
_TESTS_DIR = Path(__file__).resolve().parent
os.environ["APP_YAML_PATH"] = str(_TESTS_DIR / "app.test.yaml")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/postgres")
