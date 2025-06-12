import json
import re
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.agents.executors import call_agent_async
from api.streaming.google_stream import stream_google_agent
from api.streaming.langchain_stream import stream_langchain_agent

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"
    session_id: str = "default_session"
    model: str = "langchain-example-agent"


class ChatResponse(BaseModel):
    response: str
    status: str = "success"


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest, agents_registry: Dict, session_service):
    """Simple chat endpoint."""
    try:
        response = await call_agent_async(
            query=request.message,
            user_id=request.user_id,
            session_id=request.session_id,
            model_id=request.model,
            agents_registry=agents_registry,
            session_service=session_service,
        )
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.post("/v1/chat/completions")
async def openai_compatible_chat(request: Dict[Any, Any], agents_registry: Dict, session_service):
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

        # Get agent info
        if requested_model not in agents_registry:
            available = list(agents_registry.keys())
            raise HTTPException(status_code=404, detail=f"Model '{requested_model}' not found. Available: {available}")

        agent_info = agents_registry[requested_model]
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
                            agent_info,
                            user_query,
                            user_id,
                            session_id,
                            completion_id,
                            current_timestamp,
                            requested_model,
                            session_service,
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
                query=user_query,
                user_id=user_id,
                session_id=session_id,
                model_id=requested_model,
                agents_registry=agents_registry,
                session_service=session_service,
            )

            # Handle title generation cleanup
            if "Please generate a concise, 5-word-or-less title for the conversation" in messages[-1].get("content", ""):
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
