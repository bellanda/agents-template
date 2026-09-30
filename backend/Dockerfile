# =============================================================================
# Stage 1 — builder: install deps into an isolated /app/.venv via uv
# =============================================================================
FROM python:3.13.13-slim-trixie AS builder

WORKDIR /app

# Build the venv at the SAME absolute path it lives at runtime (/app/.venv): uv bakes absolute
# interpreter shebangs into console scripts (granian, ...); a venv built elsewhere and copied
# leaves a dangling shebang → `exec granian` fails with "executable file not found".
# Use the base image's system Python — NEVER let uv download its own interpreter into
# /root/.local (absent in the runtime stage → dangling python symlink). Pair with
# `.python-version = 3.13` (minor-only, tracks the base image).
ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON_PREFERENCE=only-system \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.11.18 /uv /uvx /bin/

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# =============================================================================
# Stage 2 — runtime: non-root, minimal apt surface, prebuilt venv on PATH
# =============================================================================
FROM python:3.13.13-slim-trixie AS runtime

# Runtime libs for OpenCV headless (image → AVIF in config/uploads.py).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

# APP_UID lets the container run AS the owner of the writable bind mount (./backend/uploads) on
# hosts where the deploy user isn't 1000 — avoids "Permission denied" without root/chown.
# GID stays pinned at 1000. Default 1000; set APP_UID in `.env` only on a non-1000 host.
ARG APP_UID=1000
RUN groupadd --system --gid 1000 app \
 && useradd  --system --uid ${APP_UID} --gid app --no-create-home --shell /sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app . /app/

# /app/uploads is shadowed by the bind mount at runtime (host ownership wins).
RUN install -d -o app -g app -m 0750 /app/uploads

# PYTHONPATH mirrors the wheel layout (hatch sources: src/api → `api`; config/agents at root).
# With uv --no-install-project these names resolve only via source roots on sys.path:
# /app/src (for `api`) + /app (for `config`, `agents`).
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src:/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app:app

# Granian is env-driven and fail-fast: every GRANIAN_* comes from compose (constants in
# compose.yaml, per-env sizing in config/docker/compose.<env>.yaml). `${VAR:?msg}` aborts the
# boot with a clear error instead of inheriting a silent guess. nginx reaches it over TCP at
# backend:8000 (upstream in config/nginx/conf.d/shared.conf).
CMD ["sh", "-c", "exec granian api.main:app \
     --interface ${GRANIAN_INTERFACE:?GRANIAN_INTERFACE not set} \
     --host 0.0.0.0 --port 8000 \
     --workers ${GRANIAN_WORKERS:?GRANIAN_WORKERS not set} \
     --loop ${GRANIAN_LOOP:?GRANIAN_LOOP not set} \
     --http ${GRANIAN_HTTP:?GRANIAN_HTTP not set} \
     --workers-lifetime ${GRANIAN_WORKERS_LIFETIME:?GRANIAN_WORKERS_LIFETIME not set} \
     --workers-max-rss ${GRANIAN_WORKERS_MAX_RSS:?GRANIAN_WORKERS_MAX_RSS not set} \
     --workers-kill-timeout ${GRANIAN_WORKERS_KILL_TIMEOUT:?GRANIAN_WORKERS_KILL_TIMEOUT not set}"]
