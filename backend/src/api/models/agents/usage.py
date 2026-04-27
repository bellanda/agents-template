import datetime as dt

from pydantic import BaseModel
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    func,
)

from api.models.metadata import metadata

agent_message_usage_table = Table(
    "agent_message_usage",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("thread_id", String(128), nullable=False, index=True),
    Column("message_id", String(64), nullable=False, index=True),
    Column("user_id", String(255), nullable=True, index=True),
    Column("client_id", String(255), nullable=True, index=True),
    Column("agent_id", String(255), nullable=False, index=True),
    Column("provider", String(64), nullable=False),
    Column("model_id", String(255), nullable=False, index=True),
    Column("input_tokens", Integer, nullable=False, server_default="0"),
    Column("cached_input_tokens", Integer, nullable=False, server_default="0"),
    Column("output_tokens", Integer, nullable=False, server_default="0"),
    Column("reasoning_tokens", Integer, nullable=False, server_default="0"),
    Column("total_tokens", Integer, nullable=False, server_default="0"),
    Column("cost_usd", Numeric(14, 8), nullable=False, server_default="0"),
    Column("error", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_agent_message_usage_created_at", "created_at"),
)


class AgentMessageUsage(BaseModel):
    thread_id: str
    message_id: str
    user_id: str | None = None
    client_id: str | None = None
    agent_id: str
    provider: str
    model_id: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None
    created_at: dt.datetime | None = None

    model_config = {"from_attributes": True}
