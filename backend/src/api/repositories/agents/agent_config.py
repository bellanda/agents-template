"""agent_configs + agent_config_versions — raw SQL, dict in/out (gate `database`)."""

from typing import Any, Final
from uuid import UUID

from asyncpg.connection import Connection

# Versions are a bounded history for the rollback UI, not a paginated collection: the newest
# N is all the screen shows, and it keeps the endpoint with a LIMIT.
MAX_VERSIONS_LISTED: Final = 50

CONFIG_COLUMNS: Final = (
    "id, tenant_id, agent_id, model_id, system_prompt_markdown, active_version, "
    "created_at, updated_at"
)


async def get_agent_config(
    conn: Connection, tenant_id: str, agent_id: str
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        f"SELECT {CONFIG_COLUMNS} FROM agent_configs WHERE tenant_id = $1 AND agent_id = $2",
        tenant_id,
        agent_id,
    )
    return dict(row) if row else None


async def upsert_agent_config(
    conn: Connection,
    *,
    tenant_id: str,
    agent_id: str,
    model_id: str,
    system_prompt_markdown: str,
) -> dict[str, Any]:
    """Write the active config and bump its version atomically (first save = version 1).

    The bump happens in SQL (`active_version + 1`) so two concurrent saves never produce the
    same version number — the UNIQUE(config_id, version) on the snapshot would reject it.
    """
    row = await conn.fetchrow(
        f"""
        INSERT INTO agent_configs (tenant_id, agent_id, model_id, system_prompt_markdown)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (tenant_id, agent_id) DO UPDATE SET
            model_id = EXCLUDED.model_id,
            system_prompt_markdown = EXCLUDED.system_prompt_markdown,
            active_version = agent_configs.active_version + 1
        RETURNING {CONFIG_COLUMNS}
        """,
        tenant_id,
        agent_id,
        model_id,
        system_prompt_markdown,
    )
    return dict(row)


async def insert_agent_config_version(
    conn: Connection,
    *,
    config_id: UUID,
    version: int,
    model_id: str,
    system_prompt_markdown: str,
    note: str | None,
    created_by: str | None,
) -> dict[str, Any]:
    row = await conn.fetchrow(
        """
        INSERT INTO agent_config_versions
            (config_id, version, model_id, system_prompt_markdown, note, created_by)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, config_id, version, model_id, system_prompt_markdown, note, created_by,
                  created_at
        """,
        config_id,
        version,
        model_id,
        system_prompt_markdown,
        note,
        created_by,
    )
    return dict(row)


async def list_agent_config_versions(conn: Connection, config_id: UUID) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT version, model_id, system_prompt_markdown, note, created_by, created_at
        FROM agent_config_versions
        WHERE config_id = $1
        ORDER BY version DESC
        LIMIT $2
        """,
        config_id,
        MAX_VERSIONS_LISTED,
    )
    return [dict(row) for row in rows]


async def get_agent_config_version(
    conn: Connection, config_id: UUID, version: int
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """
        SELECT version, model_id, system_prompt_markdown, note, created_by, created_at
        FROM agent_config_versions
        WHERE config_id = $1 AND version = $2
        """,
        config_id,
        version,
    )
    return dict(row) if row else None
