"""Sync the agents infrastructure to another FastAPI project.

Copies only the agents-specific layers. Assumes the target already follows
the same config/src/api architecture (config/, src/api/, alembic/).

Usage:
    uv run scripts/sync_agents_to_another_fastapi_project.py --target /path/to/other/backend

What gets copied:
    agents/                         → target/agents/
    src/api/core/agents/            → target/src/api/core/agents/
    src/api/models/agents/          → target/src/api/models/agents/
    src/api/repositories/agents/   → target/src/api/repositories/agents/
    src/api/services/agents/        → target/src/api/services/agents/
    src/api/routes/agents/          → target/src/api/routes/agents/

What gets printed (manual steps):
    - pyproject.toml dependencies and hatch sources to add
    - main.py lifespan and router registration snippet
    - Alembic migration commands
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

OPTIONAL_TARGETS: list[tuple[str, str]] = [
    ("src/api/__init__.py", "src/api/__init__.py"),
    ("src/api/core/database.py", "src/api/core/database.py"),
    ("config/database.py", "config/database.py"),
    ("config/paths.py", "config/paths.py"),
    ("config/tools.py", "config/tools.py"),
    ("config/__init__.py", "config/__init__.py"),
]


def copy_tree(src: Path, dst: Path, label: str) -> None:
    if not src.exists():
        print(f"  SKIP  {label} (source not found: {src})")
        return

    if dst.exists():
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


def print_post_install(target: Path) -> None:
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 MANUAL STEPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. pyproject.toml — add dependencies:

    "langchain>=1.2.10",
    "langchain-cerebras>=0.8.2",
    "langchain-community>=0.4.1",
    "langchain-core>=1.2.17",
    "langchain-google-genai>=4.2.1",
    "langchain-groq>=1.1.2",
    "langchain-nvidia-ai-endpoints>=1.1.0",
    "langchain-openai>=1.1.10",
    "langgraph>=1.0.10",
    "langgraph-checkpoint-postgres>=3.0.4",
    "markitdown[all]>=0.1.5",
    "duckpy>=2.1.1",          # only if using web_search_agent
    "orjson>=3.11.7",
    "asyncpg>=0.31.0",

2. pyproject.toml — add hatch sources (so agents/ is importable):

    [tool.hatch.build.targets.wheel]
    packages = ["config", "src/api", "agents"]   # add "agents"

    [tool.hatch.build.targets.wheel.sources]
    "agents" = "agents"                           # add this line

3. Run:

    uv sync --upgrade

4. main.py — add to lifespan and router:

    from api.core.agents.checkpointer import close_checkpointer, init_checkpointer
    from api.services.agents.registry import reload_agents_registry
    from api import agents_router  # or: from api.routes.agents import router as agents_router

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_asyncpg_pool()
        await init_checkpointer()      # add
        await reload_agents_registry() # add
        yield
        await close_checkpointer()     # add
        await close_asyncpg_pool()

    api_router.include_router(agents_router)  # add

5. src/api/__init__.py — ensure agents_router is exported:

    from api.routes.agents import router as agents_router
    __all__ = ["agents_router"]

6. Alembic — generate and apply migrations for agents tables:

    uv run alembic revision --autogenerate -m "add agents tables"
    uv run alembic upgrade head

    Required tables: checkpoints, checkpoint_writes, checkpoint_blobs, chat_history_threads

7. .env — add AI provider keys you need:

    # Pick the providers your agents use:
    OPENAI_API_KEY=
    GOOGLE_API_KEY=
    ANTHROPIC_API_KEY=
    NVIDIA_API_KEY=
    CHUTES_API_KEY=
    CEREBRAS_API_KEY=
    GROQ_API_KEY=
    OPENROUTER_API_KEY=
    DEEPSEEK_API_KEY=

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync agents infrastructure to another FastAPI project")
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

    if args.optional:
        print("\nCopying optional files (skip if already exist):")
        for src_rel, dst_rel in OPTIONAL_TARGETS:
            copy_file(HERE / src_rel, target / dst_rel, src_rel, overwrite=False)
    else:
        print("\nTip: pass --optional to also copy config/ and core/database.py stubs")

    print_post_install(target)


if __name__ == "__main__":
    main()
