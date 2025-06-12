import json
from typing import Dict

from api.agents.executors import execute_langchain_agent
from api.utils.tools import (
    generate_thinking_message,
    generate_tool_end_message,
    generate_tool_start_message,
    should_agent_process_tool_result,
)


async def stream_langchain_agent(
    agent_info: Dict,
    query: str,
    user_id: str,
    session_id: str,
    completion_id: str,
    current_timestamp: int,
    requested_model: str,
):
    """Stream LangChain agent responses with robust error handling."""
    agent = agent_info["agent"]

    if "CompiledStateGraph" in str(type(agent)):
        print("🌊 Starting LangGraph streaming...")
        config = {"configurable": {"thread_id": f"thread_{user_id}_{session_id}"}}

        tool_calls_made = []
        completed_tools = []
        all_tools_completed = False

        try:
            async for event in agent.astream_events({"messages": [("user", query)]}, config=config, version="v1"):
                event_type = event.get("event")
                event_name = event.get("name", "")

                # Log tool starts and stream progress to user
                if event_type == "on_tool_start":
                    tool_calls_made.append(event_name)
                    print(f"🔧 Tool started: {event_name}")

                    # Get tool input for context
                    tool_input = event.get("data", {}).get("input", {})

                    # Generate HPEAgents markup message
                    progress_msg = generate_tool_start_message(event_name, tool_input)

                    progress_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": current_timestamp,
                        "model": requested_model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": f"\n{progress_msg}\n"},
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

                    # Generate tool end message
                    tool_end_msg = generate_tool_end_message(tool_name, success=True)

                    tool_end_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": current_timestamp,
                        "model": requested_model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": f"\n{tool_end_msg}\n"},
                                "logprobs": None,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(tool_end_chunk)}\n\n"

                    # Check if all tools are completed and send processing message
                    if len(completed_tools) == len(tool_calls_made) and not all_tools_completed:
                        all_tools_completed = True

                        # Generate thinking message
                        thinking_msg = generate_thinking_message("Analisando resultados e preparando resposta...")

                        processing_chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": current_timestamp,
                            "model": requested_model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": f"\n{thinking_msg}\n\n---\n\n"},
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

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Streaming error: {error_msg}")

            # Check if it's the tool call history error
            if "tool_calls that do not have a corresponding ToolMessage" in error_msg:
                print("🔄 Detected tool call history error, clearing session and retrying...")

                # Try with a fresh session (new thread_id)
                fresh_config = {"configurable": {"thread_id": f"fresh_{user_id}_{session_id}_{current_timestamp}"}}

                try:
                    # Send error recovery message
                    recovery_msg = "🔄 Detectado problema no histórico, reiniciando sessão..."
                    recovery_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": current_timestamp,
                        "model": requested_model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": f"\n{recovery_msg}\n\n"},
                                "logprobs": None,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(recovery_chunk)}\n\n"

                    # Retry with fresh session
                    async for event in agent.astream_events(
                        {"messages": [("user", query)]}, config=fresh_config, version="v1"
                    ):
                        event_type = event.get("event")

                        # Stream LLM tokens only (simplified retry)
                        if event_type == "on_chat_model_stream":
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

                    print("✅ Successfully recovered from tool call history error")

                except Exception as retry_error:
                    print(f"❌ Retry also failed: {retry_error}")
                    # Fallback to non-streaming execution
                    fallback_response = await execute_langchain_agent(agent_info, query, user_id, session_id)
                    if fallback_response:
                        # Stream the fallback response
                        words = fallback_response.split()
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
            else:
                # For other errors, fallback to non-streaming execution
                print("🔄 Falling back to non-streaming execution...")
                try:
                    fallback_response = await execute_langchain_agent(agent_info, query, user_id, session_id)
                    if fallback_response:
                        # Stream the fallback response
                        words = fallback_response.split()
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
                except Exception as fallback_error:
                    print(f"❌ Fallback execution also failed: {fallback_error}")
                    # Last resort: send error message to user
                    error_response = f"❌ Desculpe, ocorreu um erro inesperado: {str(fallback_error)}"
                    error_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": current_timestamp,
                        "model": requested_model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": error_response},
                                "logprobs": None,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"
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
