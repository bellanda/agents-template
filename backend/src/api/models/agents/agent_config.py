import datetime as dt
from uuid import UUID

from pydantic import BaseModel


class AgentConfigRecord(BaseModel):
    """Active tenant instructions for one agent (table agent_configs).

    One row per (tenant_id, agent_id). The Markdown is appended at runtime to the agent's
    base system prompt by `core/agents/tenant_instructions.py`; history lives in
    agent_config_versions.
    """

    id: UUID | None = None
    tenant_id: str
    agent_id: str
    model_id: str
    system_prompt_markdown: str = ""
    active_version: int = 1
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None
