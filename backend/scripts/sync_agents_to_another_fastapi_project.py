"""Sync the agents infrastructure to another FastAPI project.

Copies only the agents-specific layers. Assumes the target already follows
the same config/src/api architecture (config/, src/api/, db/ with dbmate).

Usage:
    uv run scripts/sync_agents_to_another_fastapi_project.py --target /path/to/other/backend

What gets copied (always, overwrite — pure agents-namespaced infra):
    agents/                         → target/agents/
    src/api/core/agents/            → target/src/api/core/agents/
    src/api/models/agents/          → target/src/api/models/agents/
    src/api/repositories/agents/   → target/src/api/repositories/agents/
    src/api/services/agents/        → target/src/api/services/agents/
    src/api/routes/agents/          → target/src/api/routes/agents/

What gets copied (always, skip-if-exists — shared deps the agents infra imports;
a richer target keeps its own versions):
    src/api/middlewares/            → LoggingMiddleware (request_id + http_request line)
    src/api/models/uploads/         → UserUpload + upload_jsonb (user-owned uploads)
    src/api/repositories/uploads/   → UserUploadRepository
    src/api/core/logging.py         → structlog stack (setup/shutdown/get_logger)
    src/api/core/exceptions.py      → BadRequestError etc (HTTPException subclasses)
    src/api/services/auth.py        → get_auth_context identity seam
    src/api/routes/uploads.py       → POST /uploads (save_upload + user_uploads row)
    config/uploads.py               → canonical save_upload pipeline

    db/migrations/*.sql             → target/db/migrations/  (existing files preserved)

What gets printed (manual steps):
    - pyproject.toml dependencies and hatch sources to add
    - main.py lifespan and router registration snippet
    - dbmate migration commands
    - .env variables to add
"""

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent.parent  # backend/


COPY_TARGETS: list[tuple[str, str]] = [
    ("src/api/core/agents", "src/api/core/agents"),
    ("src/api/models/agents", "src/api/models/agents"),
    ("src/api/repositories/agents", "src/api/repositories/agents"),
    ("src/api/services/agents", "src/api/services/agents"),
    ("src/api/routes/agents", "src/api/routes/agents"),
]

# Shared infra the agents layers import. Copied ALWAYS but skip-if-exists, so a
# richer target (real auth, full logging stack, org_uploads) keeps its versions
# while a fresh target gets a working baseline. Dirs and files.
SHARED_DIRS: list[tuple[str, str]] = [
    ("src/api/middlewares", "src/api/middlewares"),
    ("src/api/models/uploads", "src/api/models/uploads"),
    ("src/api/repositories/uploads", "src/api/repositories/uploads"),
]

SHARED_FILES: list[tuple[str, str]] = [
    ("src/api/core/logging.py", "src/api/core/logging.py"),
    ("src/api/core/exceptions.py", "src/api/core/exceptions.py"),
    ("src/api/services/auth.py", "src/api/services/auth.py"),
    ("src/api/routes/uploads.py", "src/api/routes/uploads.py"),
    ("config/uploads.py", "config/uploads.py"),
]

OPTIONAL_TARGETS: list[tuple[str, str]] = [
    ("src/api/__init__.py", "src/api/__init__.py"),
    ("src/api/core/database.py", "src/api/core/database.py"),
    ("config/database.py", "config/database.py"),
    ("config/paths.py", "config/paths.py"),
    ("config/tools.py", "config/tools.py"),
    ("config/__init__.py", "config/__init__.py"),
]


def copy_tree(src: Path, dst: Path, label: str, overwrite: bool = True) -> None:
    if not src.exists():
        print(f"  SKIP  {label} (source not found: {src})")
        return

    if dst.exists():
        if not overwrite:
            print(f"  SKIP  {label} (already exists — not overwriting)")
            return
        shutil.rmtree(dst)

    shutil.copytree(src, dst)
    print(f"  OK    {label}")


def copy_file(src: Path, dst: Path, label: str, overwrite: bool = False) -> None:
    if not src.exists():
        print(f"  SKIP  {label} (source not found)")
        return

    if dst.exists() and not overwrite:
        print(f"  SKIP  {label} (already exists — not overwriting)")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  OK    {label}")


def copy_migrations(src_dir: Path, dst_dir: Path) -> None:
    """Copy dbmate migration .sql files individually — never wipe the target's own migrations."""
    if not src_dir.exists():
        print("  SKIP  db/migrations (source not found)")
        return

    dst_dir.mkdir(parents=True, exist_ok=True)
    for sql in sorted(src_dir.glob("*.sql")):
        dst = dst_dir / sql.name
        if dst.exists():
            print(f"  SKIP  db/migrations/{sql.name} (already exists)")
            continue
        shutil.copy2(sql, dst)
        print(f"  OK    db/migrations/{sql.name}")


def print_post_install(target: Path) -> None:
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 MANUAL STEPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. pyproject.toml — add dependencies:

    "langchain>=1.2.10",
    "langchain-community>=0.4.1",
    "langchain-core>=1.2.17",
    "langchain-openai>=1.1.10",   # ChatOpenRouter herda de ChatOpenAI
    "langgraph>=1.0.10",
    "langgraph-checkpoint-postgres>=3.0.4",
    "markitdown[all]>=0.1.5",
    "duckpy>=2.1.1",          # only if using web_search_agent
    "orjson>=3.11.7",
    "asyncpg>=0.31.0",
    "structlog>=25.5.0",                 # logging stack (core/logging.py)
    "opencv-python-headless>=4.13.0.92", # uploads image→AVIF (config/uploads.py)
    "numpy>=2.2.0",                      # uploads image pipeline

2. pyproject.toml — add hatch sources (so agents/ is importable):

    [tool.hatch.build.targets.wheel]
    packages = ["config", "src/api", "agents"]   # add "agents"

    [tool.hatch.build.targets.wheel.sources]
    "agents" = "agents"                           # add this line

3. Run:

    uv sync --upgrade

4. main.py — wire logging, middleware, lifespan, routers, uploads mount:

    from api.core.agents.checkpointer import close_checkpointer, init_checkpointer
    from api.core.logging import get_logger, setup_logging, shutdown_logging
    from api.middlewares.logging_middleware import LoggingMiddleware
    from api.routes.agents import agents_router
    from api.routes.uploads import router as uploads_router
    from api.services.agents.registry import reload_agents_registry
    from fastapi.staticfiles import StaticFiles
    from config.api import api_config

    setup_logging()                     # add — before app creation
    log = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_asyncpg_pool()
        await init_checkpointer()      # add
        await reload_agents_registry() # add
        yield
        await close_checkpointer()     # add
        await close_asyncpg_pool()
        shutdown_logging()             # add

    app.add_middleware(LoggingMiddleware)            # add (after CORS)
    api_router.include_router(agents_router)          # add
    api_router.include_router(uploads_router, prefix="/uploads", tags=["Uploads"])  # add
    # Mount AFTER the API router so POST /uploads wins and GETs fall through:
    app.mount(api_config.UPLOADS_HTTP_PREFIX,
              StaticFiles(directory=api_config.UPLOADS_DIR), name="uploads")

    Notes:
    - Identity: every agents/uploads route depends on `get_auth_context`
      (src/api/services/auth.py). Default is open (X-User-Id header / `user`
      query → "default_user"). Replace `resolve_identity` with real JWT.
    - Uploads: org-owned projects also need an `org_uploads` table + OrgUpload
      model/repo (this template ships user-owned only). See rule uploads.md.

5. dbmate — apply the migrations (copied above into db/migrations/):

    dbmate up

    Provides tables: agent_message_usage, chat_history, checkpoints,
    checkpoint_writes, checkpoint_blobs, user_uploads. Requires DATABASE_URL
    in .env, e.g. postgres://user:pass@localhost:5432/db?sslmode=disable

6. .env — add AI provider keys you need:

    # Pick the providers your agents use:
    OPENROUTER_API_KEY=   # gateway único de chat
    GROQ_API_KEY=         # só transcrição (Whisper)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync agents infrastructure to another FastAPI project"
    )
    parser.add_argument(
        "--target",
        required=True,
        metavar="PATH",
        help="Path to the target project's backend/ directory",
    )
    parser.add_argument(
        "--optional",
        action="store_true",
        help="Also copy optional config and database files (skipped if they already exist)",
    )
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"ERROR: target directory does not exist: {target}", file=sys.stderr)
        sys.exit(1)

    print(f"\nSource : {HERE}")
    print(f"Target : {target}\n")

    print("Copying agents layers:")
    for src_rel, dst_rel in COPY_TARGETS:
        copy_tree(HERE / src_rel, target / dst_rel, src_rel)

    print("\nCopying shared infra (skip if target already has it):")
    for src_rel, dst_rel in SHARED_DIRS:
        copy_tree(HERE / src_rel, target / dst_rel, src_rel, overwrite=False)
    for src_rel, dst_rel in SHARED_FILES:
        copy_file(HERE / src_rel, target / dst_rel, src_rel, overwrite=False)

    print("\nCopying dbmate migrations (agents + user_uploads tables):")
    copy_migrations(HERE / "db" / "migrations", target / "db" / "migrations")

    if args.optional:
        print("\nCopying optional files (skip if already exist):")
        for src_rel, dst_rel in OPTIONAL_TARGETS:
            copy_file(HERE / src_rel, target / dst_rel, src_rel, overwrite=False)
    else:
        print("\nTip: pass --optional to also copy config/ and core/database.py stubs")

    print_post_install(target)


if __name__ == "__main__":
    main()
