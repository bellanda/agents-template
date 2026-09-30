"""Sync the agents infrastructure to another FastAPI project.

Copies only the agents-specific layers. Assumes the target already follows
the same config/src/api architecture (config/, src/api/, db/ with dbmate).

Usage:
    uv run scripts/sync_agents_to_another_fastapi_project.py --target /path/to/other/backend
        [--add-module ocr --add-module media] [--optional] [--examples]

What gets overwritten (per FILE, template-owned files only — the CANONICAL layer; local edits to
a file the template owns are lost, so improvements must be made here first). Target files the
template does not have are NEVER deleted (app-specific files and adapters live there):
    src/api/core/agents/*.py        → ONLY modules that already exist in the target
                                      (an app keeps just the modules it uses; new ones need
                                      --add-module NAME, repeatable). Each kept module stays
                                      byte-identical to the template; app behavior lives in
                                      adapters OUTSIDE core/agents (domain hints go through the
                                      `extra_instructions` keyword of ocr/media).
    src/api/schemas/agents/         → per-file overwrite
    src/api/models/agents/          → per-file overwrite
    src/api/repositories/agents/    → per-file overwrite
    src/api/services/agents/        → per-file overwrite
    src/api/routes/agents/          → per-file overwrite

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

What gets copied only with --examples (skip-if-exists — the target owns its agents/):
    agents/weather_agent/           → agent with tools
    agents/web_search_agent/        → agent with tools + scraping core
    agents/research_supervisor_agent/ → subagent delegation (needs web_search_agent)

What gets printed (manual steps):
    - pyproject.toml dependencies and hatch sources to add
    - main.py lifespan and router registration snippet
    - dbmate migration commands
    - config/app/*.yaml keys + Settings fields + .env secrets to add
"""

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent.parent  # backend/


CORE_AGENTS = "src/api/core/agents"

# Layers synced per file (overwrite template-owned files, never delete target files).
COPY_TARGETS: list[tuple[str, str]] = [
    ("src/api/schemas/agents", "src/api/schemas/agents"),
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

# Documented examples of the use-case spectrum (see AGENTS_SUBSYSTEM.md §3). Never overwrite:
# `agents/` is where the target's real agents live.
EXAMPLE_AGENTS: list[str] = ["weather_agent", "web_search_agent", "research_supervisor_agent"]

OPTIONAL_TARGETS: list[tuple[str, str]] = [
    ("src/api/__init__.py", "src/api/__init__.py"),
    ("src/api/core/database.py", "src/api/core/database.py"),
    ("config/settings.py", "config/settings.py"),
    ("config/integrations.py", "config/integrations.py"),
    ("config/database.py", "config/database.py"),
    ("config/api.py", "config/api.py"),
    ("config/paths.py", "config/paths.py"),
    ("config/tools.py", "config/tools.py"),
    ("config/__init__.py", "config/__init__.py"),
]


def sync_tree_per_file(
    src: Path,
    dst: Path,
    label: str,
    *,
    only_existing: bool = False,
    add_modules: frozenset[str] = frozenset(),
) -> None:
    """Overwrite template-owned files one by one; NEVER delete anything in the target.

    WHY not rmtree+copytree (the old behavior): the target's `agents/` dirs also hold
    app-specific files and adapters that the template does not know about — wiping them
    destroyed real work.

    `only_existing` (core/agents): a module is overwritten only if the target already has it,
    because an app keeps ONLY the modules it uses (unused ones drag in deps it does not have,
    e.g. ocr.py needs pypdfium2). `add_modules` names the exceptions to add explicitly.
    An empty target `__init__.py` is app-owned and never touched.
    """
    if not src.exists():
        print(f"  SKIP  {label} (source not found: {src})")
        return

    overwritten: list[str] = []
    unchanged: list[str] = []
    added: list[str] = []
    skipped: list[str] = []
    for file in sorted(src.rglob("*")):
        if not file.is_file() or "__pycache__" in file.parts:
            continue
        rel = file.relative_to(src)
        target_file = dst / rel
        if only_existing and rel.name == "__init__.py":
            continue
        if target_file.exists():
            if target_file.read_bytes() == file.read_bytes():
                unchanged.append(str(rel))
            else:
                shutil.copy2(file, target_file)
                overwritten.append(str(rel))
        elif not only_existing or file.stem in add_modules:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target_file)
            added.append(str(rel))
        else:
            skipped.append(str(rel))

    print(f"  {label}")
    for title, names in (
        ("OVERWRITTEN", overwritten),
        ("ADDED", added),
        ("unchanged", unchanged),
        ("SKIPPED (not in target; use --add-module NAME)", skipped),
    ):
        if names:
            print(f"    {title}: {', '.join(names)}")
    unknown = sorted(add_modules - {f.stem for f in src.glob("*.py")}) if only_existing else []
    if unknown:
        print(f"    WARNING: --add-module names not in the template: {', '.join(unknown)}")


def copy_tree(src: Path, dst: Path, label: str, overwrite: bool = True) -> None:
    """Copy a whole dir only when the target lacks it (skip-if-exists). Never deletes."""
    if not src.exists():
        print(f"  SKIP  {label} (source not found: {src})")
        return

    if dst.exists():
        print(f"  SKIP  {label} (already exists — not overwriting)")
        return

    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
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
    "anyio>=4.13.0",                     # llm.py limiter/retry, ocr.py fan-out
    "curl-cffi>=0.15.0",                 # media.py (Groq Whisper multipart)
    "pypdfium2>=5.13.0",                # ocr.py (render PDF pages) — only if you use OCR
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

    Provides tables: agent_message_usage (+ tenant_id), chat_history, checkpoints,
    checkpoint_writes, checkpoint_blobs, user_uploads, agent_configs,
    agent_config_versions. Requires DATABASE_URL in .env, e.g.
    postgres://user:pass@localhost:5432/db?sslmode=disable

    EXISTING APP: review every copied .sql BEFORE `dbmate up`. The template's initial
    migration creates tables the app already has, and apps with their own org-level agent
    config (kailos/balizap `org_agent_configs`) map tenant_id to organization_id instead of
    creating agent_configs — delete what does not apply, write an app migration for the rest.

6. Config — the agents layers read ONLY `settings` / `config.integrations`, never os.getenv.
   Non-secret values go in the yaml, secrets in `.env` (skill python-config-bootstrap):

   a) config/app/{local,staging,prod}.yaml — add to ALL THREE (keep them symmetric):

      openrouter:                       # single chat gateway (text/image/video)
        api_base: https://openrouter.ai/api/v1
        site_url: ""                    # optional HTTP-Referer attribution
        app_title: ""                   # optional X-Title attribution
      agents:
        stream_debug: false             # true only in local (per-chunk previews in logs)
        max_concurrent_llm: 8           # process-wide cap on one-shot calls (core/agents/llm.py)
        llm_max_retries: 3              # transient provider errors only
        tenant_config_ttl_seconds: 30   # in-process memo of tenant instructions

      The layers also need these existing sections with the SAME names: `logging:`
      (service_name, app_env, level, format, level_asyncpg — core/logging.py) and
      `postgres.pool:` (config/database.py). Copy them from this template's yamls if missing.

   b) config/settings.py — add the sub-models + fields the layers use:

      class OpenRouterSettings(BaseModel):   # api_base, site_url, app_title (defaults in template)
      class AgentsSettings(BaseModel):       # stream_debug, max_concurrent_llm,
                                             # llm_max_retries, tenant_config_ttl_seconds
      Settings: openrouter: OpenRouterSettings = OpenRouterSettings()
                agents: AgentsSettings = AgentsSettings()
                openrouter_api_key: SecretStr | None   # from .env OPENROUTER_API_KEY
                groq_api_key: SecretStr | None         # from .env GROQ_API_KEY

   c) config/integrations.py — expose GROQ_API_KEY, OPENROUTER_API_KEY, OPENROUTER_API_BASE,
      OPENROUTER_SITE_URL, OPENROUTER_APP_TITLE (flattened from `settings`, as in this template).

   d) .env — secrets only (never in the yaml), and never the same key in both places:

      OPENROUTER_API_KEY=   # gateway único de chat
      GROQ_API_KEY=         # só transcrição (Whisper)

   e) Auth seam — `get_auth_context` MUST return "tenant_id" (services/auth.py is
      skip-if-exists, so an existing app keeps its own): the organization id in multi-tenant
      apps, the user id otherwise. Agent-config routes, tenant instructions middleware and
      per-tenant cost read it.

   f) Agents — add `tenant_instructions_middleware` (after `sliding_window_middleware`) to
      every `create_agent(middleware=[...])` that should read tenant instructions.

   g) Frontend — copy frontend/src/components/{ai-elements,chat,agent-config}/ and the
      agent-config route + lib/api.ts functions (agent config, tool results, suggestion action).

   h) Infra (only if the target lacks it): copy config/nginx/snippets/api-proxy.conf — it carries
      the long-running SSE location (`^~ /api/v1/agents/chat/`, proxy_read_timeout 300s). Without
      it nginx cuts the chat stream at the default 120s while a tool runs.

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
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Also copy the example agents under agents/ (skipped if they already exist)",
    )
    parser.add_argument(
        "--add-module",
        action="append",
        default=[],
        metavar="NAME",
        help="Add a core/agents module the target does not have yet (e.g. ocr, media). "
        "Repeatable. Without it only modules already present in the target are overwritten.",
    )
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"ERROR: target directory does not exist: {target}", file=sys.stderr)
        sys.exit(1)

    print(f"\nSource : {HERE}")
    print(f"Target : {target}\n")

    print("Syncing core/agents (only modules the target already has, plus --add-module):")
    sync_tree_per_file(
        HERE / CORE_AGENTS,
        target / CORE_AGENTS,
        CORE_AGENTS,
        only_existing=True,
        add_modules=frozenset(args.add_module),
    )

    print("\nSyncing agents layers per file (target-only files are kept):")
    for src_rel, dst_rel in COPY_TARGETS:
        sync_tree_per_file(HERE / src_rel, target / dst_rel, src_rel)

    print("\nCopying shared infra (skip if target already has it):")
    for src_rel, dst_rel in SHARED_DIRS:
        copy_tree(HERE / src_rel, target / dst_rel, src_rel, overwrite=False)
    for src_rel, dst_rel in SHARED_FILES:
        copy_file(HERE / src_rel, target / dst_rel, src_rel, overwrite=False)

    print("\nCopying dbmate migrations (agents + user_uploads tables):")
    copy_migrations(HERE / "db" / "migrations", target / "db" / "migrations")

    if args.examples:
        print("\nCopying example agents (skip if already exist):")
        for name in EXAMPLE_AGENTS:
            rel = f"agents/{name}"
            copy_tree(HERE / rel, target / rel, rel, overwrite=False)

    if args.optional:
        print("\nCopying optional files (skip if already exist):")
        for src_rel, dst_rel in OPTIONAL_TARGETS:
            copy_file(HERE / src_rel, target / dst_rel, src_rel, overwrite=False)
    else:
        print("\nTip: pass --optional to also copy config/ and core/database.py stubs")

    print_post_install(target)


if __name__ == "__main__":
    main()
