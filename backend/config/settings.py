"""Centralized settings — YAML config + .env secrets (skill `python-config-bootstrap`).

Layout:
- `config/app/{local,staging,prod}.yaml` (versioned) — every non-secret value.
- `.env` (repo root, gitignored) — secrets + `ENVIRONMENT=local|staging|prod`.

YAML resolution (first match wins):
1. `APP_YAML_PATH` — explicit override (tests point it at `backend/tests/app.test.yaml`).
2. `/app/app.yaml` — docker: compose bind-mounts `config/app/${ENVIRONMENT}.yaml` there.
3. host-only: `<repo>/config/app/{ENVIRONMENT}.yaml` (ENVIRONMENT defaults to `local`).

`settings` is instantiated at import time → the app fails fast when the yaml is missing/invalid
or a required secret is absent. Business code reads config ONLY through `settings` (or the
`config/api.py` / `config/integrations.py` shims); never `os.getenv` outside this module.

This template keeps the same section names the product apps use (`postgres`, `logging`, `cors`,
`vite`, secrets as `SecretStr`), so `core/agents` and `core/logging` copied by
`scripts/sync_agents_to_another_fastapi_project.py` read the same `settings.*` attributes.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from config.tools import getenv_or_raise_exception


def resolve_app_yaml_path() -> Path:
    if explicit := os.getenv("APP_YAML_PATH"):
        return Path(explicit)
    docker_path = Path("/app/app.yaml")
    if docker_path.is_file():
        return docker_path
    env = os.getenv("ENVIRONMENT", "local")
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "config" / "app" / f"{env}.yaml"


APP_YAML_PATH = resolve_app_yaml_path()


class PostgresPoolSettings(BaseModel):
    # `max_size` is PER PROCESS: total connections = GRANIAN_WORKERS * max_size (workers are
    # set in config/docker/compose.<env>.yaml) and must stay under Postgres `max_connections`.
    min_size: int
    max_size: int
    max_queries: int
    max_inactive_connection_lifetime: float
    command_timeout: float
    timeout: float


class PostgresSettings(BaseModel):
    """asyncpg pool kwargs. The DSN is a secret: `.env > DATABASE_URL` (host) / compose (docker)."""

    pool: PostgresPoolSettings


class LoggingSettings(BaseModel):
    service_name: str
    app_env: str
    level: str
    # "" = auto (JSON when stderr is not a TTY); or "json" / "console".
    format: str = ""
    level_asyncpg: str = "WARNING"


class CorsSettings(BaseModel):
    allow_origins: list[str]
    allow_credentials: bool
    allow_methods: list[str]
    allow_headers: list[str]
    expose_headers: list[str]
    max_age: int


class OpenRouterSettings(BaseModel):
    """OpenRouter is the single chat gateway (text + image + video). Key lives in `.env`."""

    api_base: str = "https://openrouter.ai/api/v1"
    # Optional attribution headers (HTTP-Referer / X-Title) for OpenRouter's app ranking.
    site_url: str = ""
    app_title: str = ""


class AgentsSettings(BaseModel):
    # Verbose per-chunk previews in services/agents/streaming.py. On only in local: prompts and
    # tool payloads would otherwise land in staging/prod logs.
    stream_debug: bool = False
    # Process-wide cap on concurrent LLM calls made through `core/agents/llm.py`. Without it a
    # burst (N scheduled runs, a fan-out) fires hundreds of simultaneous requests and the
    # provider 429s ALL of them — including the ones that were fine. Per PROCESS, not per run.
    max_concurrent_llm: int = 8
    # Attempts per one-shot call on TRANSIENT errors only (429/5xx/timeouts); see llm.py.
    llm_max_retries: int = 3
    # How long a tenant's agent instructions stay memoized in-process before re-reading the
    # DB. Saving through the API invalidates THIS process immediately; other workers converge
    # within the TTL (no cross-process cache in the template — add Valkey if that matters).
    tenant_config_ttl_seconds: float = 30.0


class ViteSettings(BaseModel):
    # Build-time VITE_* values. On Docker the compose.<env>.yaml `nginx.build.args` are what
    # actually decide the bundle (the image build cannot see this yaml) — keep them in sync.
    # The template frontend calls same-origin `/api/v1/...`, so these only feed the dev proxy
    # target (`VITE_BACKEND_URL` in vite.config.ts) and are kept for product apps that need
    # absolute URLs.
    backend_url: str
    frontend_url: str


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # From the yaml
    postgres: PostgresSettings
    logging: LoggingSettings
    cors: CorsSettings
    openrouter: OpenRouterSettings = OpenRouterSettings()
    agents: AgentsSettings = AgentsSettings()
    vite: ViteSettings

    # From .env. Required: the API cannot run without a database.
    database_url: SecretStr = Field(
        default_factory=lambda: SecretStr(getenv_or_raise_exception("DATABASE_URL"))
    )

    # AI providers — exactly two, and only these: OpenRouter is the gateway for ALL chat
    # (text, image, video; default model is multimodal) and Groq only does audio transcription
    # (Whisper). Optional so the app boots without them (chat then fails with a clear provider
    # error; transcription degrades to "no transcript").
    openrouter_api_key: SecretStr | None = Field(default_factory=lambda: _opt("OPENROUTER_API_KEY"))
    groq_api_key: SecretStr | None = Field(default_factory=lambda: _opt("GROQ_API_KEY"))


def _opt(key: str) -> SecretStr | None:
    value = os.getenv(key)
    return SecretStr(value) if value else None


def _load() -> Settings:
    if not APP_YAML_PATH.is_file():
        env = os.getenv("ENVIRONMENT", "local")
        raise RuntimeError(
            f"app yaml not found at {APP_YAML_PATH} (ENVIRONMENT={env}). "
            "Check that config/app/{ENVIRONMENT}.yaml exists and ENVIRONMENT in .env is "
            "local/staging/prod."
        )
    with APP_YAML_PATH.open("rb") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise RuntimeError(f"app yaml at {APP_YAML_PATH} is not a mapping at the root")
    return Settings(**data)


settings = _load()
