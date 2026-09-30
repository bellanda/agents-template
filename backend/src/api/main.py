from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import agents_router, uploads_router
from api.core.agents.checkpointer import close_checkpointer, init_checkpointer
from api.core.logging import get_logger, setup_logging, shutdown_logging
from api.middlewares.logging_middleware import LoggingMiddleware
from api.services.agents.registry import get_agents_registry, reload_agents_registry
from config.api import api_config
from config.database import close_asyncpg_pool, init_asyncpg_pool
from config.settings import settings

setup_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for the application."""
    # 1. Initialize database pool
    await init_asyncpg_pool()

    # 3. Initialize checkpointer (Postgres)
    await init_checkpointer()

    # 4. Load agents
    await reload_agents_registry()

    log.info("app_startup_complete")
    yield

    # Cleanup
    await close_checkpointer()
    await close_asyncpg_pool()
    shutdown_logging()


app = FastAPI(title="Multi-Agent LiteLLM Proxy", version="1.0.0", lifespan=lifespan)

api_router = APIRouter(prefix="/api/v1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
    expose_headers=settings.cors.expose_headers,
    max_age=settings.cors.max_age,
)
app.add_middleware(LoggingMiddleware)


@app.get("/")
async def root(agents_registry: dict = Depends(get_agents_registry)):
    """API status and available models."""
    available_models = list(agents_registry.keys())
    return {
        "message": "Multi-Agent LiteLLM Proxy is running",
        "available_models": available_models,
        "total_agents": len(available_models),
        "agents_by_type": {"langchain": available_models},
    }


@app.get("/health")
async def health_check(agents_registry: dict = Depends(get_agents_registry)):
    """Health check endpoint."""
    return {"status": "healthy", "agents_loaded": len(agents_registry)}


api_router.include_router(agents_router)
api_router.include_router(uploads_router, prefix="/uploads", tags=["Uploads"])
app.include_router(api_router)

# Serve persisted attachments. Mounted AFTER the API router so the POST handler
# at the same prefix wins; GETs fall through to the static directory.
app.mount(
    api_config.UPLOADS_HTTP_PREFIX,
    StaticFiles(directory=api_config.UPLOADS_DIR),
    name="uploads",
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
