import datetime as dt

from pydantic import BaseModel


class AgentMessageUsage(BaseModel):
    thread_id: str
    message_id: str
    user_id: str | None = None
    client_id: str | None = None
    tenant_id: str | None = None
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
