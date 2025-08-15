import json
from typing import Dict


async def stream_langchain_agent(
    agent_info: Dict,
    query: str,
    user_id: str,
    session_id: str,
    completion_id: str,
    current_timestamp: int,
    requested_model: str,
    verbose: bool = False,
):
    """Stream LangChain AgentExecutor responses (tokens or high-level events) in real time."""
    agent = agent_info["agent"]  # Deve ser sempre AgentExecutor
    try:
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": query}]},
            version="v1",
            config={"configurable": {"thread_id": session_id}},
        ):
            event_type = event.get("event")
            # Início de ferramenta
            if event_type == "on_tool_start":
                tool_name = event.get("name", "ferramenta")
                tool_input = event.get("data", {}).get("input", {})
                args_str = ", ".join(f"{k}={v}" for k, v in tool_input.items())
                msg = f"🛠️ Iniciando ferramenta: `{tool_name}`\n> Argumentos: {args_str}\n\n"
                chunk_data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": current_timestamp,
                    "model": requested_model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": msg},
                            "logprobs": None,
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
            # Fim de ferramenta
            elif event_type == "on_tool_end":
                msg = "🧠 Processando resultado da ferramenta...\n\n"
                chunk_data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": current_timestamp,
                    "model": requested_model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": msg},
                            "logprobs": None,
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
            # Início da resposta do modelo (só se não for tool_call)
            elif event_type == "on_chat_model_start":
                # Só mostrar se NÃO for chamada de função/tool
                data = event.get("data", {})
                chunk = data.get("chunk")
                # Se chunk tiver tool_calls, não mostrar nada
                if chunk and hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    continue
                continue
            # Stream do conteúdo do modelo
            elif event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                content = getattr(chunk, "content", None)
                if content:
                    chunk_data = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": current_timestamp,
                        "model": requested_model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": content},
                                "logprobs": None,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
            # Ignorar outros eventos
    except Exception as e:
        error_msg = f"❌ Streaming error: {str(e)}"
        error_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": current_timestamp,
            "model": requested_model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": error_msg},
                    "logprobs": None,
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
