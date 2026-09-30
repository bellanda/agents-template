import datetime as dt
from uuid import UUID

from pydantic import BaseModel


class AgentConfigVersion(BaseModel):
    """Immutable snapshot of an agent config (table agent_config_versions). One row per save."""

    id: UUID | None = None
    config_id: UUID
    version: int
    model_id: str
    system_prompt_markdown: str = ""
    note: str | None = None
    created_by: str | None = None
    created_at: dt.datetime | None = None
