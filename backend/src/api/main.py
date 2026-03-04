from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import agents_router
from api.core.agents.checkpointer import close_checkpointer, init_checkpointer
from api.services.agents.registry import get_agents_registry, reload_agents_registry
from config.database import close_asyncpg_pool, init_asyncpg_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for the application."""
    # 1. Initialize database pool
    await init_asyncpg_pool()

    # 3. Initialize checkpointer (Postgres)
    await init_checkpointer()

    # 4. Load agents
    await reload_agents_registry()

    yield

    # Cleanup
    await close_checkpointer()
    await close_asyncpg_pool()


app = FastAPI(title="Multi-Agent LiteLLM Proxy", version="1.0.0", lifespan=lifespan)

api_router = APIRouter(prefix="/api/v1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
