import datetime as dt
from typing import Any

from pydantic import BaseModel, Field


class AgentCheckpoint(BaseModel):
    thread_id: str
    checkpoint_ns: str = ""
    checkpoint_id: str
    parent_checkpoint_id: str | None = None
    checkpoint: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: dt.datetime | None = None


class AgentCheckpointWrite(BaseModel):
    thread_id: str
    checkpoint_ns: str = ""
    checkpoint_id: str
    task_id: str
    task_path: str = ""
    idx: int
    channel: str
    blob: Any | None = None
