"""Tenant agent config: read-or-default, save-as-new-version, rollback.

Save and rollback always create a NEW version (never mutate history), so "restore v3" is
itself auditable and reversible. Every write invalidates this process's memo of the
instructions (`core/agents/tenant_instructions.py`); other workers converge within
`settings.agents.tenant_config_ttl_seconds`.
"""

from typing import Any

from asyncpg.connection import Connection

from api.core.agents import model_catalog
from api.core.agents.prompt_cache import prompt_cache
from api.core.agents.tenant_instructions import tenant_instructions_cache_key
from api.core.exceptions import BadRequestError, NotFoundError
from api.repositories.agents.agent_config import (
    get_agent_config,
    get_agent_config_version,
    insert_agent_config_version,
    list_agent_config_versions,
    upsert_agent_config,
)

NEVER_SAVED_VERSION = 0


def config_response(tenant_id: str, agent_id: str, row: dict[str, Any] | None) -> dict[str, Any]:
    """API shape; a synthesized default (version 0, empty Markdown) when never saved."""
    if row is None:
        return {
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "model_id": model_catalog.DEFAULT_MODEL_ID,
            "system_prompt_markdown": "",
            "active_version": NEVER_SAVED_VERSION,
            "updated_at": None,
        }
    return {
        "agent_id": agent_id,
        "tenant_id": tenant_id,
        "model_id": row["model_id"],
        "system_prompt_markdown": row["system_prompt_markdown"],
        "active_version": row["active_version"],
        "updated_at": row["updated_at"],
    }


async def get_config_or_default(conn: Connection, tenant_id: str, agent_id: str) -> dict[str, Any]:
    return config_response(tenant_id, agent_id, await get_agent_config(conn, tenant_id, agent_id))


async def save_config_version(
    conn: Connection,
    *,
    tenant_id: str,
    agent_id: str,
    system_prompt_markdown: str,
    model_id: str | None,
    note: str | None,
    created_by: str | None,
) -> dict[str, Any]:
    """Upsert the active config + snapshot, in one transaction. Raises BadRequestError for a
    model outside the catalog (a slug without configured credentials would fail later, far
    from the screen where it was chosen)."""
    current = await get_agent_config(conn, tenant_id, agent_id)
    resolved_model = model_id or (current or {}).get("model_id") or model_catalog.DEFAULT_MODEL_ID
    if not model_catalog.exists(resolved_model):
        raise BadRequestError(f"Modelo {resolved_model!r} não está disponível.")

    async with conn.transaction():
        row = await upsert_agent_config(
            conn,
            tenant_id=tenant_id,
            agent_id=agent_id,
            model_id=resolved_model,
            system_prompt_markdown=system_prompt_markdown,
        )
        await insert_agent_config_version(
            conn,
            config_id=row["id"],
            version=row["active_version"],
            model_id=resolved_model,
            system_prompt_markdown=system_prompt_markdown,
            note=note,
            created_by=created_by,
        )
    prompt_cache.invalidate(tenant_instructions_cache_key(tenant_id, agent_id))
    return config_response(tenant_id, agent_id, row)


async def list_config_versions(
    conn: Connection, tenant_id: str, agent_id: str
) -> list[dict[str, Any]]:
    current = await get_agent_config(conn, tenant_id, agent_id)
    if current is None:
        return []
    return await list_agent_config_versions(conn, current["id"])


async def activate_config_version(
    conn: Connection, *, tenant_id: str, agent_id: str, version: int, created_by: str | None
) -> dict[str, Any]:
    """Restore `version` as a NEW version. Raises NotFoundError if it does not exist."""
    current = await get_agent_config(conn, tenant_id, agent_id)
    snapshot = await get_agent_config_version(conn, current["id"], version) if current else None
    if snapshot is None:
        raise NotFoundError(f"Versão {version} não encontrada.")
    return await save_config_version(
        conn,
        tenant_id=tenant_id,
        agent_id=agent_id,
        system_prompt_markdown=snapshot["system_prompt_markdown"],
        model_id=snapshot["model_id"] if model_catalog.exists(snapshot["model_id"]) else None,
        # Shown verbatim as the note in the pt-BR version history (frontend VersionsPanel).
        note=f"Restaurada da v{version}",
        created_by=created_by,
    )
