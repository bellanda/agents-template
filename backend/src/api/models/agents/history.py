import datetime as dt
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, String, Table, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB

from api.models.metadata import metadata

chat_history_table = Table(
    "chat_history",
    metadata,
    Column("thread_id", String(128), primary_key=True),
    Column("user_id", String(255), nullable=False, index=True),
    Column("client_id", String(255), nullable=True, index=True),
    Column("agent_id", String(255), nullable=False, index=True),
    Column("messages", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("preview", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
)


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
