import time

from fastapi import APIRouter, Depends

from api.services.agents.registry import get_agents_registry

router = APIRouter()


@router.get("/v1/models")
async def list_models(agents_registry: dict = Depends(get_agents_registry)):
    """List available models in OpenAI format."""
    models = []
    for model_id, agent_info in agents_registry.items():
        models.append(
            {
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "multi-agent-proxy",
                "permission": [],
                "root": model_id,
                "parent": None,
                "description": agent_info.get("description"),
            }
        )

    return {"object": "list", "data": models}
