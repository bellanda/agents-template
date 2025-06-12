from fastapi import APIRouter, HTTPException

from api.agents.discovery import discover_agents

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reload-agents")
async def reload_agents(session_service):
    """Reload all agents."""
    try:
        new_agents_registry = discover_agents(session_service)
        return {
            "status": "success",
            "message": f"Reloaded {len(new_agents_registry)} agents",
            "agents": list(new_agents_registry.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload agents: {str(e)}")
