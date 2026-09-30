import datetime as dt
from typing import Final

from pydantic import BaseModel, Field

# Mirrors ck_agent_configs_markdown_length (migration) and MAX_PROMPT_MARKDOWN_CHARS in the
# frontend (lib/api.ts). ~20k chars is ~5k tokens: generous for business instructions, and a
# ceiling on how much every single model call of the tenant pays in input tokens.
MAX_PROMPT_MARKDOWN_CHARS: Final = 20_000
MAX_NOTE_CHARS: Final = 500


class AgentConfigUpdate(BaseModel):
    system_prompt_markdown: str = Field(max_length=MAX_PROMPT_MARKDOWN_CHARS)
    # Must be in core/agents/model_catalog.py; omitted = keep the current/default model.
    model_id: str | None = None
    note: str | None = Field(default=None, max_length=MAX_NOTE_CHARS)


class AgentConfigResponse(BaseModel):
    agent_id: str
    tenant_id: str
    model_id: str
    system_prompt_markdown: str
    # 0 = never saved (synthesized default).
    active_version: int
    updated_at: dt.datetime | None = None


class AgentConfigVersionResponse(BaseModel):
    version: int
    model_id: str
    system_prompt_markdown: str
    note: str | None = None
    created_by: str | None = None
    created_at: dt.datetime


class AgentConfigVersionsResponse(BaseModel):
    versions: list[AgentConfigVersionResponse]
