import time

from fastapi import APIRouter, Depends

from api.services.agents.registry import get_agents_registry

router = APIRouter()


@router.get("")
async def list_models(agents_registry: dict = Depends(get_agents_registry)):
    """List available models in OpenAI format, including agent mode."""
    # The registry is already loaded and cached by the dependency
    models = []
    current_time = int(time.time())

    for model_id, agent_info in agents_registry.items():
        models.append(
            {
                "id": model_id,
                "object": "model",
                "created": current_time,
                "owned_by": "multi-agent-proxy",
                "permission": [],
                "root": model_id,
                "parent": None,
                "name": agent_info.get("name", model_id),
                "description": agent_info.get("description"),
                "mode": agent_info.get("mode", "single-shot"),
                "suggestions": agent_info.get("suggestions", []),
            }
        )

    return {"object": "list", "data": models}
