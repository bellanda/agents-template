from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.services.agents.registry import get_agents_registry
from config.checkpointer import get_checkpointer

router = APIRouter()


@router.get("/threads")
async def list_threads(
    agent_id: str | None = None,
    agents_registry: dict = Depends(get_agents_registry),
) -> dict[str, Any]:
    """List all conversation threads, optionally filtered by agent_id."""
    checkpointer = get_checkpointer()
    if checkpointer is None:
        return {"threads": []}

    threads: list[dict[str, Any]] = []
    seen_thread_ids: set[str] = set()

    try:
        async for checkpoint_tuple in checkpointer.alist({}):
            try:
                config = getattr(checkpoint_tuple, "config", None)
                if config is None:
                    continue
                if not isinstance(config, dict):
                    continue
                try:
                    configurable = config.get("configurable")
                except KeyError:
                    configurable = None
                if isinstance(configurable, dict):
                    thread_id = configurable.get("thread_id", "")
                else:
                    thread_id = ""

                if not thread_id or thread_id in seen_thread_ids:
                    continue
                seen_thread_ids.add(thread_id)

                metadata = getattr(checkpoint_tuple, "metadata", None) or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                checkpoint = getattr(checkpoint_tuple, "checkpoint", None) or {}
                if not isinstance(checkpoint, dict):
                    checkpoint = {}
                created_at = checkpoint.get("ts", "")

                thread_agent_id = metadata.get("agent_id", "")

                if agent_id and thread_agent_id and thread_agent_id != agent_id:
                    continue

                channel_values = checkpoint.get("channel_values", {})
                if not isinstance(channel_values, dict):
                    channel_values = {}
                messages = channel_values.get("messages", [])
                if not isinstance(messages, list):
                    messages = []
                preview = ""
                if messages:
                    first_human = next(
                        (getattr(m, "content", str(m)) for m in messages if getattr(m, "type", "") == "human"),
                        "",
                    )
                    if isinstance(first_human, str):
                        preview = first_human[:100]

                threads.append(
                    {
                        "thread_id": thread_id,
                        "agent_id": thread_agent_id,
                        "preview": preview,
                        "message_count": len(messages),
                        "created_at": created_at,
                    }
                )
            except KeyError as e:
                print(f"❌ Error listing threads (skip checkpoint): {e}")
                continue
            except Exception as e:
                print(f"❌ Error listing threads (skip checkpoint): {e}")
                continue
    except (KeyError, Exception) as e:
        print(f"❌ Error listing threads: {e}")

    # Sort by creation time (most recent first)
    threads.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    return {"threads": threads}


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    agents_registry: dict = Depends(get_agents_registry),
) -> dict[str, Any]:
    """Get the message history for a specific thread."""
    checkpointer = get_checkpointer()
    if checkpointer is None:
        raise HTTPException(status_code=503, detail="Checkpointer not initialized")

    # Find a chat-mode agent to use for get_state
    chat_agent = None
    for agent_info in agents_registry.values():
        if agent_info.get("mode") == "chat":
            chat_agent = agent_info["agent"]
            break

    if chat_agent is None:
        raise HTTPException(status_code=404, detail="No chat-mode agent available")

    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = await chat_agent.aget_state(config)

        if state is None or state.values is None:
            raise HTTPException(status_code=404, detail="Thread not found")

        messages = state.values.get("messages", [])

        serialized_messages = []
        for msg in messages:
            serialized_messages.append(
                {
                    "role": getattr(msg, "type", "unknown"),
                    "content": getattr(msg, "content", str(msg)),
                    "id": getattr(msg, "id", ""),
                }
            )

        return {
            "thread_id": thread_id,
            "messages": serialized_messages,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str) -> dict[str, str]:
    """Delete all checkpoints for a specific thread."""
    checkpointer = get_checkpointer()
    if checkpointer is None:
        raise HTTPException(status_code=503, detail="Checkpointer not initialized")

    try:
        # Delete thread using the checkpointer's delete method
        if hasattr(checkpointer, "adelete_thread"):
            await checkpointer.adelete_thread(thread_id)
        elif hasattr(checkpointer, "delete_thread"):
            checkpointer.delete_thread(thread_id)
        else:
            # Fallback: manually delete via SQL if method not available
            if hasattr(checkpointer, "conn"):
                await checkpointer.conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
                await checkpointer.conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
                await checkpointer.conn.commit()

        return {"status": "deleted", "thread_id": thread_id}
    except Exception as e:
        print(f"❌ Error deleting thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
