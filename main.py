from typing import Any, Dict

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.adk.sessions import InMemorySessionService

from api.agents.discovery import discover_agents
from api.agents.executors import call_agent_async
from api.routes.admin import reload_agents
from api.routes.chat import ChatRequest, ChatResponse, openai_compatible_chat
from api.routes.models import list_models
from api.utils.tools import (
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

# Global services
session_service = InMemorySessionService()
agents_registry = {}


def get_agents_registry():
    """Dependency to get agents registry."""
    return agents_registry


def get_session_service():
    """Dependency to get session service."""
    return session_service


# Initialize agents on startup
@app.on_event("startup")
async def startup_event():
    """Initialize agents on startup."""
    global agents_registry

    startup_msg = generate_status_message("processing", "Initializing Multi-Agent Proxy...")
    print(f"🚀 {startup_msg}")

    agents_registry = discover_agents(session_service)

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
    google_agents = [k for k, v in agents_registry.items() if v.get("type") == "google"]
    langchain_agents = [k for k, v in agents_registry.items() if v.get("type") == "langchain"]

    return {
        "message": "Multi-Agent LiteLLM Proxy is running",
        "available_models": available_models,
        "total_agents": len(available_models),
        "google_agents": len(google_agents),
        "langchain_agents": len(langchain_agents),
        "agents_by_type": {"google": google_agents, "langchain": langchain_agents},
    }


@app.get("/health")
async def health_check(agents_registry: dict = Depends(get_agents_registry)):
    """Health check endpoint."""
    health_msg = generate_status_message("completed", "Health check passed")
    print(f"💚 {health_msg}")

    return {"status": "healthy", "agents_loaded": len(agents_registry)}


# Chat endpoints
@app.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    request: ChatRequest, agents_registry: dict = Depends(get_agents_registry), session_service=Depends(get_session_service)
):
    """Simple chat endpoint."""
    try:
        response = await call_agent_async(
            query=request.message,
            user_id=request.user_id,
            session_id=request.session_id,
            model_id=request.model,
            agents_registry=agents_registry,
            session_service=session_service,
        )
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.post("/v1/chat/completions")
async def openai_chat_completions(
    request: Dict[Any, Any],
    agents_registry: dict = Depends(get_agents_registry),
    session_service=Depends(get_session_service),
):
    """OpenAI-compatible endpoint for LibreChat integration."""
    return await openai_compatible_chat(request, agents_registry, session_service)


# Models endpoint
@app.get("/v1/models")
async def list_available_models(agents_registry: dict = Depends(get_agents_registry)):
    """List available models in OpenAI format."""
    models_msg = generate_result_message("success", f"Listing {len(agents_registry)} available models")
    print(f"📋 {models_msg}")

    return await list_models(agents_registry)


# Admin endpoints
@app.post("/admin/reload-agents")
async def reload_all_agents(session_service=Depends(get_session_service)):
    """Reload all agents."""
    global agents_registry
    try:
        reload_msg = generate_status_message("processing", "Reloading all agents...")
        print(f"🔄 {reload_msg}")

        result = await reload_agents(session_service)
        # Update global registry after reload
        agents_registry = discover_agents(session_service)

        reload_success_msg = generate_result_message("success", "All agents reloaded successfully")
        print(f"✅ {reload_success_msg}")

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload agents: {str(e)}")


if __name__ == "__main__":
    startup_thinking = generate_thinking_message("Preparing to start the Multi-Agent Proxy server...")
    print(f"\n💭 {startup_thinking}")

    server_start_msg = generate_status_message("processing", "Starting Multi-Agent Proxy...")
    print(f"🚀 {server_start_msg}")

    uvicorn.run(app, host="0.0.0.0", port=8073)
