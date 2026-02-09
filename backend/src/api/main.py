from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.agents import router as agents_router
from api.services.agents.history import init_db
from api.services.agents.registry import get_agents_registry, reload_agents_registry
from api.services.agents.tools import (
    generate_status_message,
    generate_thinking_message,
)
from config.checkpointer import close_checkpointer, init_checkpointer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for the application."""
    # Startup: initialize history DB, SQLite checkpointer, then load agents
    init_db()
    await init_checkpointer()
    # Pre-load agents immediately so the first request is fast
    await reload_agents_registry()
    yield
    # Shutdown: close the checkpointer connection
    await close_checkpointer()


# Initialize FastAPI app
app = FastAPI(title="Multi-Agent LiteLLM Proxy", version="1.0.0", lifespan=lifespan)

api_router = APIRouter(prefix="/api/v1")

# CORS middleware for frontend compatibility
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
    thinking_msg = generate_thinking_message("Preparing agent information for display...")
    print(f"💭 {thinking_msg}")

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
    health_msg = generate_status_message("completed", "Health check passed")
    print(f"💚 {health_msg}")

    return {"status": "healthy", "agents_loaded": len(agents_registry)}


# Register routers
api_router.include_router(agents_router)
app.include_router(api_router)


if __name__ == "__main__":
    startup_thinking = generate_thinking_message("Preparing to start the Multi-Agent Proxy server...")
    print(f"\n💭 {startup_thinking}")

    server_start_msg = generate_status_message("processing", "Starting Multi-Agent Proxy...")
    print(f"🚀 {server_start_msg}")

    uvicorn.run(app, host="0.0.0.0", port=8000)
