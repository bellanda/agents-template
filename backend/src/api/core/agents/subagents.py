"""Subagent delegation — a supervisor agent calls specialist agents as TOOLS.

When to use (vs. one agent with many tools): the specialist needs its own system prompt, its
own tool set or a long tool loop whose intermediate messages would bloat the supervisor's
context. The supervisor only sees the specialist's FINAL answer — that is the whole point.
Example: `agents/research_supervisor_agent/`.

Three invariants this module encodes:

* **Stateless specialist.** Built with `checkpointer=False`: invoked inside the supervisor's
  tool, a subgraph would otherwise INHERIT the supervisor's checkpointer and persist its inner
  loop under the chat thread. The supervisor's own checkpoint already records the delegation.
* **Not streamed to the user.** Every run of the specialist carries `SUBAGENT_RUN_TAG`;
  `services/agents/streaming.py` drops events with it, otherwise the specialist's tokens would
  be typed into the chat bubble as if the supervisor wrote them.
* **Still billed.** Callbacks and metadata propagate through the tool call (same thread_id /
  tenant_id), so `usage_recorder` records the specialist's calls; `agent_id` gets a
  `:<specialist>` suffix so cost per specialist is queryable.
"""

from typing import Any, Final

from langchain_core.runnables import Runnable, RunnableConfig

from api.services.agents.executors import normalize_chunk_text

SUBAGENT_RUN_TAG: Final = "nostream"


async def run_subagent(
    subagent: Runnable, task: str, *, name: str, parent_config: RunnableConfig
) -> str:
    """Run `subagent` on `task` to completion and return its final text answer."""
    metadata: dict[str, Any] = dict(parent_config.get("metadata") or {})
    metadata["agent_id"] = f"{metadata.get('agent_id', 'agent')}:{name}"
    result = await subagent.ainvoke(
        {"messages": [{"role": "user", "content": task}]},
        config={
            "callbacks": parent_config.get("callbacks"),
            "metadata": metadata,
            "tags": [SUBAGENT_RUN_TAG],
            "run_name": name,
        },
    )
    messages = result.get("messages") or []
    return normalize_chunk_text(messages[-1].content) if messages else ""
