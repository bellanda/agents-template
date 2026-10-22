"""aprune_thread_history keeps only the latest checkpoint and the thread still resumes (2026-10-22).

Real LangGraph graph + the real asyncpg saver: after pruning, the next turn still sees every
earlier message (memory = latest checkpoint only). Source: kailos prod, 94% of checkpoint rows
were superseded; the helper is template-owned and synced to every app.
"""

from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from api.core.agents.asyncpg_saver import AsyncpgCheckpointSaver
from config.database import get_pool


@pytest.mark.asyncio
async def test_pruned_thread_resumes_with_the_full_message_history(db_engine):
    # Real pool (committed rows): the saver runs writes concurrently, which one test connection
    # cannot do. The thread is deleted at the end.
    pool = await get_pool()
    saver = AsyncpgCheckpointSaver(pool)
    seen_lengths: list[int] = []

    def echo(state: MessagesState):
        seen_lengths.append(len(state["messages"]))
        return {"messages": [AIMessage(content=f"echo {len(state['messages'])}")]}

    graph = (
        StateGraph(MessagesState)
        .add_node("echo", echo)
        .add_edge(START, "echo")
        .add_edge("echo", END)
        .compile(checkpointer=saver)
    )
    thread = f"prune-{uuid4()}"
    config = {"configurable": {"thread_id": thread}}
    try:
        for text in ("one", "two", "three"):
            await graph.ainvoke({"messages": [HumanMessage(content=text)]}, config)
        count_sql = "SELECT count(*) FROM checkpoints WHERE thread_id=$1"
        before = await pool.fetchval(count_sql, thread)
        assert before > 1
        assert await saver.aprune_thread_history(thread) == before - 1
        assert await pool.fetchval(count_sql, thread) == 1
        assert await saver.aprune_thread_history("missing-" + thread) == 0
        result = await graph.ainvoke({"messages": [HumanMessage(content="four")]}, config)
    finally:
        await saver.adelete_thread(thread)
    assert seen_lengths == [1, 3, 5, 7]
    assert [m.content for m in result["messages"] if m.type == "human"] == [
        "one",
        "two",
        "three",
        "four",
    ]
