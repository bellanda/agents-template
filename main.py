import json
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from google_agents.weather_agent.agent import root_agent as weather_agent

app = FastAPI(title="Weather Agent LiteLLM Proxy", version="1.0.0")

# Add CORS middleware for LibreChat compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your LibreChat domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up session service and runner
session_service = InMemorySessionService()
runner = Runner(agent=weather_agent, app_name="weather_app", session_service=session_service)


# Request/Response models for the API
class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"
    session_id: str = "default_session"


class ChatResponse(BaseModel):
    response: str
    status: str = "success"


# Helper function for agent interaction
async def call_agent_async(query: str, user_id: str, session_id: str) -> str:
    """Sends a query to the agent and returns the final response."""
    print(f">>> User Query: {query}")

    # Create session if needed
    try:
        session_service.create_session(app_name="weather_app", user_id=user_id, session_id=session_id)
    except Exception:
        pass  # Session might already exist

    # Prepare the user's message
    content = types.Content(role="user", parts=[types.Part(text=query)])

    final_response_text = "Agent did not produce a final response."

    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response_text = event.content.parts[0].text
                break
    except Exception as runner_error:
        if "Session not found" in str(runner_error):
            # Try with simplified session ID
            simple_session_id = f"session_{abs(hash(session_id)) % 10000}"
            try:
                session_service.create_session(app_name="weather_app", user_id=user_id, session_id=simple_session_id)
                async for event in runner.run_async(user_id=user_id, session_id=simple_session_id, new_message=content):
                    if event.is_final_response():
                        if event.content and event.content.parts:
                            final_response_text = event.content.parts[0].text
                        break
            except Exception:
                raise Exception(f"Agent execution failed: {runner_error}")
        else:
            raise Exception(f"Agent execution failed: {runner_error}")

    print(f"<<< Agent Response: {final_response_text}")
    return final_response_text


@app.get("/")
async def root():
    return {"message": "Weather Agent LiteLLM Proxy is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent": "weather_agent_litellm"}


@app.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """Chat endpoint for LibreChat integration."""
    try:
        response = await call_agent_async(query=request.message, user_id=request.user_id, session_id=request.session_id)
        return ChatResponse(response=response)
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


# OpenAI-compatible endpoint for LibreChat
@app.post("/v1/chat/completions")
async def openai_compatible_chat(request: Dict[Any, Any]):
    """OpenAI-compatible endpoint for LibreChat integration."""
    import time
    import uuid

    try:
        # Extract the last message from the OpenAI format
        messages = request.get("messages", [])
        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        last_message = messages[-1]
        user_query = last_message.get("content", "")

        if "Please generate a concise, 5-word-or-less title for the conversation" in user_query:
            user_query = "Please generate a concise, 5-word-or-less title for the conversation /no_think"

        # Get the requested model and stream setting
        requested_model = request.get("model", "weather-agent-qwen3-4b")
        stream = request.get("stream", False)

        # Use a default user/session for this endpoint
        user_id = "librechat_user"
        session_id = f"librechat_session_{requested_model}"

        # Generate proper OpenAI-compatible response
        current_timestamp = int(time.time())
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"

        if stream:
            # Return streaming response - direct from agent without any delays
            async def generate_stream():
                # Setup session
                try:
                    session_service.create_session(app_name="weather_app", user_id=user_id, session_id=session_id)
                except Exception:
                    pass  # Session might already exist

                # Send initial chunk with role
                initial_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": current_timestamp,
                    "model": requested_model,
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "logprobs": None, "finish_reason": None}],
                }
                yield f"data: {json.dumps(initial_chunk)}\n\n"

                # Prepare the user's message
                content = types.Content(role="user", parts=[types.Part(text=user_query)])

                try:
                    # Stream events from the agent - send response as fast as possible
                    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
                        # Send ANY content immediately, no filtering or comparison
                        if hasattr(event, "content") and event.content and event.content.parts:
                            event_text = event.content.parts[0].text

                            if event_text:  # If there's any text, send it immediately
                                # Check if this is a LibreChat title generation request
                                is_librechat_title = (
                                    "Please generate a concise, 5-word-or-less title for the conversation" in user_query
                                )

                                # Clean <think> tags only for title generation requests
                                if is_librechat_title and event_text:
                                    import re

                                    # Remove <think> blocks completely
                                    cleaned_text = re.sub(r"<think>.*?</think>", "", event_text, flags=re.DOTALL)
                                    # Remove any remaining <think> or </think> tags
                                    cleaned_text = re.sub(r"</?think>", "", cleaned_text)
                                    # Clean up extra whitespace and get last meaningful line
                                    cleaned_text = cleaned_text.strip()
                                    if cleaned_text:
                                        lines = [line.strip() for line in cleaned_text.split("\n") if line.strip()]
                                        if lines:
                                            cleaned_text = lines[-1]  # Take the last non-empty line as title
                                    event_text = cleaned_text if cleaned_text else event_text

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

                            # Check if this is the final response to break
                            if event.is_final_response():
                                break

                except Exception as runner_error:
                    # Fallback with simplified session ID
                    if "Session not found" in str(runner_error):
                        try:
                            simple_session_id = f"session_{abs(hash(session_id)) % 10000}"
                            session_service.create_session(
                                app_name="weather_app", user_id=user_id, session_id=simple_session_id
                            )

                            async for event in runner.run_async(
                                user_id=user_id, session_id=simple_session_id, new_message=content
                            ):
                                # Send ANY content immediately in fallback too
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
                        except Exception:
                            # Send error message
                            error_msg = "I apologize, but I encountered an error processing your request."
                            chunk_data = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": current_timestamp,
                                "model": requested_model,
                                "choices": [
                                    {"index": 0, "delta": {"content": error_msg}, "logprobs": None, "finish_reason": None}
                                ],
                            }
                            yield f"data: {json.dumps(chunk_data)}\n\n"

                # Send final chunk with finish_reason
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
            # Non-streaming: use the original logic
            agent_response = await call_agent_async(query=user_query, user_id=user_id, session_id=session_id)

            # Check if this is a LibreChat title generation request and clean response
            is_librechat_title = "Please generate a concise, 5-word-or-less title for the conversation" in user_query
            if is_librechat_title and agent_response:
                import re

                # Remove <think> blocks completely
                cleaned_response = re.sub(r"<think>.*?</think>", "", agent_response, flags=re.DOTALL)
                # Remove any remaining <think> or </think> tags
                cleaned_response = re.sub(r"</?think>", "", cleaned_response)
                # Clean up extra whitespace and get last meaningful line
                cleaned_response = cleaned_response.strip()
                if cleaned_response:
                    lines = [line.strip() for line in cleaned_response.split("\n") if line.strip()]
                    if lines:
                        cleaned_response = lines[-1]  # Take the last non-empty line as title
                agent_response = cleaned_response if cleaned_response else agent_response

            if not agent_response or agent_response.strip() == "":
                agent_response = "I apologize, but I couldn't generate a proper response. Please try again."

            # Calculate token usage (approximate)
            prompt_tokens = len(user_query.split()) if user_query else 0
            completion_tokens = len(agent_response.split()) if agent_response else 0

            # Return in exact OpenAI format (non-streaming)
            response_data = {
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

            return response_data

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in OpenAI endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


# Add models endpoint for LibreChat to discover available models
@app.get("/v1/models")
async def list_models():
    """List available models for LibreChat integration."""
    import time

    current_timestamp = int(time.time())

    return {
        "object": "list",
        "data": [
            {
                "id": "weather-agent-qwen3-4b",
                "object": "model",
                "created": current_timestamp,
                "owned_by": "google-adk",
                "permission": [],
                "root": "weather-agent-qwen3-4b",
                "parent": None,
            },
        ],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
