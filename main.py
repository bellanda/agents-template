import importlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

app = FastAPI(title="Multi-Agent LiteLLM Proxy", version="1.0.0")

# CORS middleware for LibreChat compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global registries
agents_registry = {}
session_service = InMemorySessionService()


def should_agent_process_tool_result(tool_name: str) -> bool:
    """Determine if a tool's result should be processed by the agent or streamed directly."""

    # Tools that return raw data that needs agent processing/formatting
    agent_processed_tools = {
        "get_weather",
        "weather",
        "clima",
        "calculator",
        "calc",
        "calculadora",
        "translator",
        "translate",
        "tradutor",
        "database_query",
        "db_query",
        "sql_query",
        "api_call",
        "api_request",
        "data_analyzer",
        "analyze_data",
        "web_search",  # Moved here - web search results need agent processing when return_direct=False
        "search",
        "busca",
    }

    # Tools that return user-ready content that can be streamed directly
    # Only include tools that have return_direct=True or are meant for direct streaming
    direct_stream_tools = {
        "file_reader",
        "read_file",
        "ler_arquivo",
        "email_sender",
        "send_email",
        "enviar_email",
        "image_generator",
        "generate_image",
        "gerar_imagem",
    }

    # Check if tool should be processed by agent
    if tool_name.lower() in agent_processed_tools:
        return True

    # Check if tool can be streamed directly
    if tool_name.lower() in direct_stream_tools:
        return False

    # Default: let agent process unknown tools for safety
    return True


def generate_tool_progress_message(tool_name: str, stage: str, tool_input: dict = None) -> str:
    """Generate dynamic progress messages based on tool name and stage."""

    # Tool name mappings for better user-friendly names
    tool_mappings = {
        "get_weather": {"name": "clima", "icon": "🌤️", "action": "consultando"},
        "web_search": {"name": "busca web", "icon": "🔍", "action": "pesquisando"},
        "search": {"name": "busca", "icon": "🔍", "action": "buscando"},
        "calculator": {"name": "calculadora", "icon": "🧮", "action": "calculando"},
        "database_query": {"name": "banco de dados", "icon": "🗄️", "action": "consultando"},
        "api_call": {"name": "API externa", "icon": "🌐", "action": "chamando"},
        "file_reader": {"name": "arquivo", "icon": "📄", "action": "lendo"},
        "email_sender": {"name": "email", "icon": "📧", "action": "enviando"},
        "image_generator": {"name": "imagem", "icon": "🎨", "action": "gerando"},
        "translator": {"name": "tradutor", "icon": "🌍", "action": "traduzindo"},
    }

    # Get tool info or create generic one
    tool_info = tool_mappings.get(tool_name, {"name": tool_name.replace("_", " "), "icon": "🔧", "action": "executando"})

    if stage == "start":
        # Add context from tool input if available
        context = ""
        if tool_input:
            # Weather-related context
            if "city" in tool_input or "cidade" in tool_input:
                city = tool_input.get("city") or tool_input.get("cidade")
                context = f" para {city}"
            # Search-related context
            elif "query" in tool_input or "consulta" in tool_input:
                query = tool_input.get("query") or tool_input.get("consulta")
                query_preview = str(query)[:30]
                context = f": '{query_preview}...'" if len(str(query)) > 30 else f": '{query}'"
            # URL-related context
            elif "url" in tool_input:
                context = f" em {tool_input['url']}"
            # File-related context
            elif "file" in tool_input or "arquivo" in tool_input:
                file_name = tool_input.get("file") or tool_input.get("arquivo")
                context = f": {file_name}"
            # Email-related context
            elif "to" in tool_input or "para" in tool_input:
                recipient = tool_input.get("to") or tool_input.get("para")
                context = f" para {recipient}"
            # Calculation context
            elif "expression" in tool_input or "expressao" in tool_input:
                expr = tool_input.get("expression") or tool_input.get("expressao")
                expr_preview = str(expr)[:20]
                context = f": {expr_preview}..." if len(str(expr)) > 20 else f": {expr}"
            # Generic context for any other input
            elif len(tool_input) > 0:
                # Get first meaningful value
                for key, value in tool_input.items():
                    if value and str(value).strip():
                        value_preview = str(value)[:25]
                        context = f": {value_preview}..." if len(str(value)) > 25 else f": {value}"
                        break

        return f"{tool_info['icon']} {tool_info['action'].capitalize()} {tool_info['name']}{context}..."

    elif stage == "error":
        return f"❌ Erro ao executar {tool_info['name']}"

    else:
        return f"🔧 Processando {tool_info['name']}..."


def discover_agents() -> Dict[str, Any]:
    """Discover all agents in google_agents and langchain_agents directories."""
    agents = {}

    # Discover Google agents
    google_path = Path("google_agents")
    if google_path.exists():
        for agent_dir in google_path.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
                agent_file = agent_dir / "agent.py"
                if agent_file.exists():
                    try:
                        module_path = f"google_agents.{agent_dir.name}.agent"
                        agent_module = importlib.import_module(module_path)

                        if hasattr(agent_module, "root_agent"):
                            agent = agent_module.root_agent
                            model_id = f"google-{agent_dir.name}".replace("_", "-")
                            runner = Runner(agent=agent, app_name=f"{agent_dir.name}_app", session_service=session_service)

                            agents[model_id] = {
                                "agent": agent,
                                "runner": runner,
                                "name": agent.name,
                                "description": agent.description,
                                "agent_dir": agent_dir.name,
                                "type": "google",
                            }
                            print(f"✓ Google agent: {model_id}")
                    except Exception as e:
                        print(f"✗ Failed to load Google agent {agent_dir.name}: {e}")

    # Discover LangChain agents
    langchain_path = Path("langchain_agents")
    if langchain_path.exists():
        for agent_dir in langchain_path.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
                agent_file = agent_dir / "agent.py"
                if agent_file.exists():
                    try:
                        module_path = f"langchain_agents.{agent_dir.name}.agent"
                        agent_module = importlib.import_module(module_path)

                        if hasattr(agent_module, "root_agent"):
                            agent = agent_module.root_agent
                            model_id = f"langchain-{agent_dir.name}".replace("_", "-")
                            agent_name = getattr(agent_module, "AGENT_NAME", agent_dir.name)
                            agent_description = getattr(
                                agent_module, "AGENT_DESCRIPTION", f"LangChain agent: {agent_dir.name}"
                            )

                            agents[model_id] = {
                                "agent": agent,
                                "runner": None,
                                "name": agent_name,
                                "description": agent_description,
                                "agent_dir": agent_dir.name,
                                "type": "langchain",
                            }
                            print(f"✓ LangChain agent: {model_id}")
                    except Exception as e:
                        print(f"✗ Failed to load LangChain agent {agent_dir.name}: {e}")

    return agents


# Initialize agents
agents_registry = discover_agents()


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"
    session_id: str = "default_session"
    model: str = "langchain-example-agent"


class ChatResponse(BaseModel):
    response: str
    status: str = "success"


def get_agent_info(model_id: str) -> Dict[str, Any]:
    """Get agent information by model ID."""
    if model_id not in agents_registry:
        available = list(agents_registry.keys())
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found. Available: {available}")
    return agents_registry[model_id]


async def execute_google_agent(agent_info: Dict, query: str, user_id: str, session_id: str) -> str:
    """Execute Google agent and return response."""
    runner = agent_info["runner"]
    app_name = f"{agent_info['agent_dir']}_app"

    # Create session if needed
    try:
        session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    except Exception:
        pass  # Session might already exist

    content = types.Content(role="user", parts=[types.Part(text=query)])

    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts:
                return event.content.parts[0].text
    except Exception as e:
        if "Session not found" in str(e):
            # Retry with simplified session ID
            simple_session_id = f"session_{abs(hash(session_id)) % 10000}"
            session_service.create_session(app_name=app_name, user_id=user_id, session_id=simple_session_id)
            async for event in runner.run_async(user_id=user_id, session_id=simple_session_id, new_message=content):
                if event.is_final_response() and event.content and event.content.parts:
                    return event.content.parts[0].text
        raise Exception(f"Google agent execution failed: {e}")

    return "No response from agent"


async def execute_langchain_agent(agent_info: Dict, query: str, user_id: str, session_id: str) -> str:
    """Execute LangChain agent and return response."""
    agent = agent_info["agent"]

    try:
        print("🔧 Executing LangChain agent...")

        # LangGraph agents
        if "CompiledStateGraph" in str(type(agent)):
            print("🚀 Using LangGraph interface")
            config = {"configurable": {"thread_id": f"thread_{user_id}_{session_id}"}}
            if hasattr(agent, "ainvoke"):
                response = await agent.ainvoke({"messages": [("user", query)]}, config=config)
            else:
                response = agent.invoke({"messages": [("user", query)]}, config=config)
        # Traditional LangChain agents
        elif hasattr(agent, "ainvoke"):
            print("🚀 Using ainvoke method")
            response = await agent.ainvoke({"input": query})
        elif hasattr(agent, "invoke"):
            print("🚀 Using invoke method")
            response = agent.invoke({"input": query})
        else:
            raise Exception("Agent has no compatible invoke method")

        print(f"📤 Raw response type: {type(response)}")

        # Extract response content
        if isinstance(response, dict):
            if "messages" in response and response["messages"]:
                print(f"📨 Found {len(response['messages'])} messages in response")
                last_message = response["messages"][-1]
                final_content = last_message.content if hasattr(last_message, "content") else str(last_message)
                print("📝 Extracted content from last message")
                return final_content
            else:
                final_content = response.get("output", response.get("result", str(response)))
                print("📝 Extracted from dict keys")
                return final_content
        else:
            print("📝 Using direct string conversion")
            return str(response)

    except Exception as e:
        print(f"❌ LangChain execution error: {e}")
        raise Exception(f"LangChain agent execution failed: {e}")


async def call_agent_async(query: str, user_id: str, session_id: str, model_id: str) -> str:
    """Execute agent and return response."""
    agent_info = get_agent_info(model_id)
    agent_type = agent_info.get("type")

    print("\n🤖 === AGENT EXECUTION ===")
    print(f"📋 Agent: {model_id} ({agent_type})")
    print(f"💬 User Query: {query}")

    if agent_type == "google":
        response = await execute_google_agent(agent_info, query, user_id, session_id)
    elif agent_type == "langchain":
        response = await execute_langchain_agent(agent_info, query, user_id, session_id)
    else:
        raise Exception(f"Unknown agent type: {agent_type}")

    print(f"✅ Final Response: {response[:150]}{'...' if len(response) > 150 else ''}")
    return response


async def stream_google_agent(
    agent_info: Dict,
    query: str,
    user_id: str,
    session_id: str,
    completion_id: str,
    current_timestamp: int,
    requested_model: str,
):
    """Stream Google agent responses."""
    runner = agent_info["runner"]
    app_name = f"{agent_info['agent_dir']}_app"

    try:
        session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    except Exception:
        pass

    content = types.Content(role="user", parts=[types.Part(text=query)])

    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if hasattr(event, "content") and event.content and event.content.parts:
                event_text = event.content.parts[0].text
                if event_text:
                    chunk_data = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": current_timestamp,
                        "model": requested_model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": event_text},
                                "logprobs": None,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"

            if event.is_final_response():
                break

    except Exception as e:
        if "Session not found" in str(e):
            # Retry with simplified session
            simple_session_id = f"session_{abs(hash(session_id)) % 10000}"
            session_service.create_session(app_name=app_name, user_id=user_id, session_id=simple_session_id)
            async for event in runner.run_async(user_id=user_id, session_id=simple_session_id, new_message=content):
                if hasattr(event, "content") and event.content and event.content.parts:
                    event_text = event.content.parts[0].text
                    if event_text:
                        chunk_data = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": current_timestamp,
                            "model": requested_model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": event_text},
                                    "logprobs": None,
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"

                if event.is_final_response():
                    break


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


@app.get("/")
async def root():
    """API status and available models."""
    available_models = list(agents_registry.keys())
    google_agents = [k for k, v in agents_registry.items() if v.get("type") == "google"]
    langchain_agents = [k for k, v in agents_registry.items() if v.get("type") == "langchain"]

    return {
        "message": "Multi-Agent LiteLLM Proxy is running",
        "available_models": available_models,
        "total_agents": len(available_models),
        "google_agents": len(google_agents),
        "langchain_agents": len(langchain_agents),
        "agents_by_type": {"google": google_agents, "langchain": langchain_agents},
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agents_loaded": len(agents_registry)}


@app.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """Simple chat endpoint."""
    try:
        response = await call_agent_async(
            query=request.message, user_id=request.user_id, session_id=request.session_id, model_id=request.model
        )
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.post("/v1/chat/completions")
async def openai_compatible_chat(request: Dict[Any, Any]):
    """OpenAI-compatible endpoint for LibreChat integration."""
    print("\n📨 === INCOMING REQUEST ===")
    print(f"🤖 Model: {request.get('model', 'unknown')}")
    print(f"🌊 Stream: {request.get('stream', False)}")

    try:
        # Extract request data
        messages = request.get("messages", [])
        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        user_query = messages[-1].get("content", "")
        requested_model = request.get("model", "")
        stream = request.get("stream", False)

        if not requested_model:
            raise HTTPException(status_code=400, detail="No model specified")

        print(f"💬 User Query: {user_query}")
        print(f"📊 Messages in conversation: {len(messages)}")

        # Handle title generation requests
        if "Please generate a concise, 5-word-or-less title for the conversation" in user_query:
            user_query = "Please generate a concise, 5-word-or-less title for the conversation /no_think"

        agent_info = get_agent_info(requested_model)
        user_id = "librechat_user"
        session_id = f"librechat_session_{requested_model}"

        # Generate response metadata
        current_timestamp = int(time.time())
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"

        if stream:
            print("🌊 Streaming response...")

            async def generate_stream():
                # Initial chunk
                initial_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": current_timestamp,
                    "model": requested_model,
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "logprobs": None, "finish_reason": None}],
                }
                yield f"data: {json.dumps(initial_chunk)}\n\n"

                try:
                    if agent_info.get("type") == "google":
                        async for chunk in stream_google_agent(
                            agent_info, user_query, user_id, session_id, completion_id, current_timestamp, requested_model
                        ):
                            yield chunk
                    else:
                        async for chunk in stream_langchain_agent(
                            agent_info, user_query, user_id, session_id, completion_id, current_timestamp, requested_model
                        ):
                            yield chunk

                except Exception as error:
                    print(f"❌ Streaming error: {error}")

                    # Send user-friendly error message with markdown
                    error_msg = "❌ Ocorreu um erro durante o processamento. Tentando novamente..."
                    error_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": current_timestamp,
                        "model": requested_model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": f"\n> ⚠️ **{error_msg}**\n\n"},
                                "logprobs": None,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"

                # Final chunk
                final_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": current_timestamp,
                    "model": requested_model,
                    "choices": [{"index": 0, "delta": {}, "logprobs": None, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/plain; charset=utf-8",
                    "X-Accel-Buffering": "no",
                    "Transfer-Encoding": "chunked",
                },
            )
        else:
            print("📄 Non-streaming response...")
            agent_response = await call_agent_async(
                query=user_query, user_id=user_id, session_id=session_id, model_id=requested_model
            )

            # Handle title generation cleanup
            if "Please generate a concise, 5-word-or-less title for the conversation" in messages[-1].get("content", ""):
                import re

                cleaned_response = re.sub(r"<think>.*?</think>", "", agent_response, flags=re.DOTALL)
                cleaned_response = re.sub(r"</?think>", "", cleaned_response).strip()
                if cleaned_response:
                    lines = [line.strip() for line in cleaned_response.split("\n") if line.strip()]
                    if lines:
                        cleaned_response = lines[-1]
                agent_response = cleaned_response if cleaned_response else agent_response

            if not agent_response or agent_response.strip() == "":
                agent_response = "I apologize, but I couldn't generate a proper response. Please try again."

            # Calculate token usage (approximate)
            prompt_tokens = len(user_query.split()) if user_query else 0
            completion_tokens = len(agent_response.split()) if agent_response else 0

            return {
                "id": completion_id,
                "object": "chat.completion",
                "created": current_timestamp,
                "model": requested_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": agent_response},
                        "logprobs": None,
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                "system_fingerprint": None,
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.get("/v1/models")
async def list_models():
    """List available models in OpenAI format."""
    models = []
    for model_id, agent_info in agents_registry.items():
        models.append(
            {
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "multi-agent-proxy",
                "permission": [],
                "root": model_id,
                "parent": None,
            }
        )

    return {"object": "list", "data": models}


@app.post("/admin/reload-agents")
async def reload_agents():
    """Reload all agents."""
    global agents_registry
    try:
        agents_registry = discover_agents()
        return {
            "status": "success",
            "message": f"Reloaded {len(agents_registry)} agents",
            "agents": list(agents_registry.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload agents: {str(e)}")


if __name__ == "__main__":
    print(f"\n🚀 Starting Multi-Agent Proxy with {len(agents_registry)} agents")
    uvicorn.run(app, host="0.0.0.0", port=8000)
