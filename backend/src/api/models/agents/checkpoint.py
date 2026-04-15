import datetime as dt
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, LargeBinary, String, Table, func, text
from sqlalchemy.dialects.postgresql import JSONB

from api.models.metadata import metadata

agent_checkpoints_table = Table(
    "checkpoints",
    metadata,
    Column("thread_id", String, primary_key=True),
    Column("checkpoint_ns", String, primary_key=True, server_default=text("''")),
    Column("checkpoint_id", String, primary_key=True),
    Column("parent_checkpoint_id", String, nullable=True),
    Column("type", String, nullable=True),
    Column("checkpoint", JSONB, nullable=False),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


class AgentCheckpoint(BaseModel):
    thread_id: str
    checkpoint_ns: str = ""
    checkpoint_id: str
    parent_checkpoint_id: str | None = None
    checkpoint: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: dt.datetime | None = None


agent_checkpoint_writes_table = Table(
    "checkpoint_writes",
    metadata,
    Column("thread_id", String, primary_key=True),
    Column("checkpoint_ns", String, primary_key=True, server_default=text("''")),
    Column("checkpoint_id", String, primary_key=True),
    Column("task_id", String, primary_key=True),
    Column("task_path", String, nullable=False, server_default=text("''")),
    Column("idx", Integer, primary_key=True),
    Column("channel", String, nullable=False),
    Column("type", String, nullable=True),
    Column("blob", LargeBinary, nullable=True),
)


class AgentCheckpointWrite(BaseModel):
    thread_id: str
    checkpoint_ns: str = ""
    checkpoint_id: str
    task_id: str
    task_path: str = ""
    idx: int
    channel: str
    blob: Any | None = None


agent_checkpoint_blobs_table = Table(
    "checkpoint_blobs",
    metadata,
    Column("thread_id", String, primary_key=True),
    Column("checkpoint_ns", String, primary_key=True, server_default=text("''")),
    Column("channel", String, primary_key=True),
    Column("version", String, primary_key=True),
    Column("type", String, nullable=False),
    Column("blob", LargeBinary, nullable=True),
)
