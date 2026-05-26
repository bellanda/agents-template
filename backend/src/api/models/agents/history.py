import datetime as dt
from typing import Any

from pydantic import BaseModel, Field


class ChatHistoryThread(BaseModel):
    thread_id: str
    user_id: str
    client_id: str | None = None
    agent_id: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    preview: str | None = None
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None

    model_config = {"from_attributes": True}
