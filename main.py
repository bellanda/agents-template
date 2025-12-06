import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.agents import router as agents_router
from api.services.agents.discovery import discover_agents
from api.services.agents.registry import get_agents_registry, set_agents_registry
from api.services.agents.tools import (
    generate_result_message,
    generate_status_message,
    generate_step_message,
    generate_thinking_message,
)

# Initialize FastAPI app
app = FastAPI(title="Multi-Agent LiteLLM Proxy", version="1.0.0")

# CORS middleware for LibreChat compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize agents on startup
@app.on_event("startup")
async def startup_event():
    """Initialize agents on startup."""
    startup_msg = generate_status_message("processing", "Initializing Multi-Agent Proxy...")
    print(f"🚀 {startup_msg}")

    agents_registry = discover_agents()
    set_agents_registry(agents_registry)

    agents_loaded_msg = generate_result_message("success", f"Loaded {len(agents_registry)} agents")
    print(f"✅ {agents_loaded_msg}")

    # Print loaded agents
    for model_id, agent_info in agents_registry.items():
        agent_step_msg = generate_step_message(1, f"{model_id} ({agent_info['type']}): {agent_info['name']}")
        print(f"  - {agent_step_msg}")


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
app.include_router(agents_router)


if __name__ == "__main__":
    startup_thinking = generate_thinking_message("Preparing to start the Multi-Agent Proxy server...")
    print(f"\n💭 {startup_thinking}")

    server_start_msg = generate_status_message("processing", "Starting Multi-Agent Proxy...")
    print(f"🚀 {server_start_msg}")

    uvicorn.run(app, host="0.0.0.0", port=8073)
