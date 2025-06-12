import json
from typing import Dict

from api.agents.executors import execute_langchain_agent
from api.utils.tools import generate_tool_progress_message, should_agent_process_tool_result


async def stream_langchain_agent(
    agent_info: Dict,
    query: str,
    user_id: str,
    session_id: str,
    completion_id: str,
    current_timestamp: int,
    requested_model: str,
):
    """Stream LangChain agent responses."""
    agent = agent_info["agent"]

    if "CompiledStateGraph" in str(type(agent)):
        print("🌊 Starting LangGraph streaming...")
        config = {"configurable": {"thread_id": f"thread_{user_id}_{session_id}"}}

        tool_calls_made = []
        completed_tools = []
        all_tools_completed = False

        async for event in agent.astream_events({"messages": [("user", query)]}, config=config, version="v1"):
            event_type = event.get("event")
            event_name = event.get("name", "")

            # Log tool starts and stream progress to user
            if event_type == "on_tool_start":
                tool_calls_made.append(event_name)
                print(f"🔧 Tool started: {event_name}")

                # Get tool input for context
                tool_input = event.get("data", {}).get("input", {})

                # Generate dynamic progress message with markdown formatting
                progress_msg = generate_tool_progress_message(event_name, "start", tool_input)

                progress_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": current_timestamp,
                    "model": requested_model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": f"\n> *{progress_msg}*\n\n"},
                            "logprobs": None,
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(progress_chunk)}\n\n"

            # Handle tool results - let agent process them for better formatting
            elif event_type == "on_tool_end":
                tool_name = event_name
                tool_output = event.get("data", {}).get("output", "")
                completed_tools.append(tool_name)
                print(f"🔧 Tool completed: {tool_name}")

                # Don't send completion messages - they're redundant
                # The next step or final response makes it clear the tool completed

                # Check if all tools are completed and send processing message
                if len(completed_tools) == len(tool_calls_made) and not all_tools_completed:
                    all_tools_completed = True
                    processing_msg = "🤔 Processando informações e preparando resposta..."
                    processing_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": current_timestamp,
                        "model": requested_model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": f"\n> *{processing_msg}*\n\n---\n\n"},
                                "logprobs": None,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(processing_chunk)}\n\n"

                if tool_output:
                    content = tool_output.content if hasattr(tool_output, "content") else str(tool_output)

                    # Determine if tool result should be processed by agent or streamed directly
                    if should_agent_process_tool_result(tool_name):
                        continue  # Let the agent process and format the response
                    else:
                        # Stream the result directly for tools that return user-ready content
                        if content:
                            chunk_data = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": current_timestamp,
                                "model": requested_model,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {"content": f"\n{content}\n"},
                                        "logprobs": None,
                                        "finish_reason": None,
                                    }
                                ],
                            }
                            yield f"data: {json.dumps(chunk_data)}\n\n"

            # Stream LLM tokens
            elif event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk", {})
                if hasattr(chunk, "content") and chunk.content:
                    chunk_data = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": current_timestamp,
                        "model": requested_model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": chunk.content},
                                "logprobs": None,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"

        print(f"🔧 Tools used: {', '.join(tool_calls_made) if tool_calls_made else 'None'}")
    else:
        # Fallback for traditional LangChain agents
        response = await execute_langchain_agent(agent_info, query, user_id, session_id)
        if response:
            # Stream in chunks
            words = response.split()
            chunk_size = 10
            for i in range(0, len(words), chunk_size):
                chunk_words = words[i : i + chunk_size]
                chunk_text = " ".join(chunk_words) + (" " if i + chunk_size < len(words) else "")
                chunk_data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": current_timestamp,
                    "model": requested_model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": chunk_text},
                            "logprobs": None,
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
