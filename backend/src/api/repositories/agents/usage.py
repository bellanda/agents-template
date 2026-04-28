from typing import Any

from asyncpg.connection import Connection
from langchain_core.messages import AIMessage

from api.core.agents.models import canonical_provider, compute_cost_usd, find_model_config
from api.models.agents.usage import AgentMessageUsage


def build_usage_from_ai_message(
    ai: AIMessage | None,
    *,
    thread_id: str,
    message_id: str,
    agent_id: str,
    user_id: str | None = None,
    client_id: str | None = None,
) -> AgentMessageUsage | None:
    """Build an AgentMessageUsage row from a finished AIMessage (response_metadata + usage_metadata).

    Returns None if the message has no usage_metadata or no provider/model info — the registry
    needs both to compute cost via compute_cost_usd.
    """
    if ai is None:
        return None
    usage = getattr(ai, "usage_metadata", None) or {}
    if not usage:
        return None
    rm = getattr(ai, "response_metadata", None) or {}
    provider = rm.get("model_provider")
    model_id = rm.get("model_name") or rm.get("model")
    if not provider or not model_id:
        return None

    cfg = find_model_config(str(provider), str(model_id))
    cost_usd = compute_cost_usd(usage, cfg) if cfg else 0.0
    in_det = usage.get("input_token_details") or {}
    out_det = usage.get("output_token_details") or {}
    return AgentMessageUsage(
        thread_id=thread_id,
        message_id=message_id,
        user_id=user_id,
        client_id=client_id,
        agent_id=agent_id,
        provider=canonical_provider(str(provider)),
        model_id=str(model_id),
        input_tokens=int(usage.get("input_tokens") or 0),
        cached_input_tokens=int(in_det.get("cache_read") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        reasoning_tokens=int(out_det.get("reasoning") or 0),
        total_tokens=int(usage.get("total_tokens") or 0),
        cost_usd=cost_usd,
    )


async def insert_agent_message_usage(conn: Connection, usage: AgentMessageUsage) -> dict[str, Any]:
    """Persist one row per LLM invocation. Receives Pydantic, returns raw dict to confirm execution."""
    row = await conn.fetchrow(
        """
        INSERT INTO agent_message_usage (
            thread_id, message_id, user_id, client_id, agent_id, provider, model_id,
            input_tokens, cached_input_tokens, output_tokens, reasoning_tokens, total_tokens,
            cost_usd, error
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        RETURNING id, thread_id, message_id, agent_id, provider, model_id,
                  input_tokens, cached_input_tokens, output_tokens, reasoning_tokens,
                  total_tokens, cost_usd, error, created_at
        """,
        usage.thread_id,
        usage.message_id,
        usage.user_id,
        usage.client_id,
        usage.agent_id,
        usage.provider,
        usage.model_id,
        usage.input_tokens,
        usage.cached_input_tokens,
        usage.output_tokens,
        usage.reasoning_tokens,
        usage.total_tokens,
        usage.cost_usd,
        usage.error,
    )
    return dict(row)


async def get_thread_total_cost_usd(conn: Connection, thread_id: str) -> float:
    """Sum cost across all messages in a thread."""
    val = await conn.fetchval(
        "SELECT COALESCE(SUM(cost_usd), 0)::float FROM agent_message_usage WHERE thread_id = $1",
        thread_id,
    )
    return float(val or 0.0)


async def get_user_total_cost_usd(conn: Connection, user_id: str) -> float:
    """Sum cost across all threads of a user."""
    val = await conn.fetchval(
        "SELECT COALESCE(SUM(cost_usd), 0)::float FROM agent_message_usage WHERE user_id = $1",
        user_id,
    )
    return float(val or 0.0)
