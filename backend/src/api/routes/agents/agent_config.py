"""Tenant agent instructions (under /agents/{agent_id}/config).

One Markdown per (tenant, agent), built in ChatGPT and pasted on the frontend screen
(`components/agent-config/`), versioned with rollback. Tenant scope comes from the auth seam
(`ctx["tenant_id"]`), never from the body. Apps with roles add their permission check here
(kailos/balizap: `agent_config:read|manage`).
"""

from asyncpg import Connection
from fastapi import APIRouter, Depends

from api.core.exceptions import NotFoundError
from api.schemas.agents.agent_config import (
    AgentConfigResponse,
    AgentConfigUpdate,
    AgentConfigVersionsResponse,
)
from api.services.agents import agent_config as agent_config_service
from api.services.agents.registry import get_agents_registry
from api.services.auth import get_auth_context
from config.database import get_conn

router = APIRouter(tags=["Agent Config"])


def ensure_agent_exists(agent_id: str, registry: dict) -> None:
    if agent_id not in registry:
        raise NotFoundError(f"Agente {agent_id!r} não encontrado.")


@router.get("/{agent_id}/config")
async def get_agent_config(
    agent_id: str,
    ctx: dict = Depends(get_auth_context),
    registry: dict = Depends(get_agents_registry),
    conn: Connection = Depends(get_conn),
) -> AgentConfigResponse:
    """Current tenant config for the agent (synthesized default if never saved)."""
    ensure_agent_exists(agent_id, registry)
    row = await agent_config_service.get_config_or_default(conn, ctx["tenant_id"], agent_id)
    return AgentConfigResponse(**row)


@router.put("/{agent_id}/config")
async def update_agent_config(
    agent_id: str,
    data: AgentConfigUpdate,
    ctx: dict = Depends(get_auth_context),
    registry: dict = Depends(get_agents_registry),
    conn: Connection = Depends(get_conn),
) -> AgentConfigResponse:
    """Save a new version (+ snapshot) and invalidate the runtime memo."""
    ensure_agent_exists(agent_id, registry)
    row = await agent_config_service.save_config_version(
        conn,
        tenant_id=ctx["tenant_id"],
        agent_id=agent_id,
        system_prompt_markdown=data.system_prompt_markdown,
        model_id=data.model_id,
        note=data.note,
        created_by=ctx["user_id"],
    )
    return AgentConfigResponse(**row)


@router.get("/{agent_id}/config/versions")
async def list_agent_config_versions(
    agent_id: str,
    ctx: dict = Depends(get_auth_context),
    registry: dict = Depends(get_agents_registry),
    conn: Connection = Depends(get_conn),
) -> AgentConfigVersionsResponse:
    """Newest-first version history (bounded, see MAX_VERSIONS_LISTED)."""
    ensure_agent_exists(agent_id, registry)
    rows = await agent_config_service.list_config_versions(conn, ctx["tenant_id"], agent_id)
    return AgentConfigVersionsResponse(versions=rows)


@router.post("/{agent_id}/config/versions/{version}/activate")
async def activate_agent_config_version(
    agent_id: str,
    version: int,
    ctx: dict = Depends(get_auth_context),
    registry: dict = Depends(get_agents_registry),
    conn: Connection = Depends(get_conn),
) -> AgentConfigResponse:
    """Restore a past version as the current config (as a new version bump)."""
    ensure_agent_exists(agent_id, registry)
    row = await agent_config_service.activate_config_version(
        conn,
        tenant_id=ctx["tenant_id"],
        agent_id=agent_id,
        version=version,
        created_by=ctx["user_id"],
    )
    return AgentConfigResponse(**row)
