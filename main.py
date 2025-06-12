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
    print("🚀 Initializing Multi-Agent Proxy...")
    agents_registry = discover_agents(session_service)
    print(f"✅ Loaded {len(agents_registry)} agents")

    # Print loaded agents
    for model_id, agent_info in agents_registry.items():
        print(f"  - {model_id} ({agent_info['type']}): {agent_info['name']}")


@app.get("/")
async def root(agents_registry: dict = Depends(get_agents_registry)):
    """API status and available models."""
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
    return await list_models(agents_registry)


# Admin endpoints
@app.post("/admin/reload-agents")
async def reload_all_agents(session_service=Depends(get_session_service)):
    """Reload all agents."""
    global agents_registry
    try:
        result = await reload_agents(session_service)
        # Update global registry after reload
        agents_registry = discover_agents(session_service)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload agents: {str(e)}")


if __name__ == "__main__":
    print("\n🚀 Starting Multi-Agent Proxy...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
