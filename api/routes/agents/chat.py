import base64
import json
import mimetypes
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.services.agents.executors import call_agent_async
from api.services.agents.registry import get_agents_registry
from api.services.agents.streaming import stream_agent
from api.services.agents.utils import convert_file_to_text

router = APIRouter()


class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    model: str
    stream: bool = False
    session_id: Optional[str] = None
    user: Optional[str] = None
    files: Optional[List[str]] = None  # Optional list of file paths to process


async def _process_files(files: List[str] | None, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process attached files.
    - Images: Converted to base64 and added as image_url parts (multimodal).
    - Documents: Converted to text using MarkItDown and appended to text content.
    """
    if not files:
        return messages

    if not messages:
        return messages

    last_msg = messages[-1]
    if last_msg.get("role") != "user":
        # If last message isn't user, append a new user message
        last_msg = {"role": "user", "content": ""}
        messages.append(last_msg)

    # Ensure content is a list if we are going to add parts
    original_content = last_msg.get("content", "")
    content_parts = []

    if isinstance(original_content, str):
        if original_content:
            content_parts.append({"type": "text", "text": original_content})
    elif isinstance(original_content, list):
        content_parts.extend(original_content)

    for file_path in files:
        mime_type, _ = mimetypes.guess_type(file_path)

        # Handle Images (Multimodal)
        if mime_type and mime_type.startswith("image/"):
            try:
                with open(file_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                    content_parts.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded_string}"}})
            except Exception as e:
                print(f"❌ Error processing image {file_path}: {e}")
                content_parts.append({"type": "text", "text": f"\n[Error processing image {file_path}: {e}]\n"})

        # Handle Text/Documents (MarkItDown)
        else:
            text = convert_file_to_text(file_path)
            if text:
                content_parts.append(
                    {
                        "type": "text",
                        "text": f"\n\n--- Conteúdo do arquivo {file_path} ---\n{text}\n-----------------------------------\n",
                    }
                )

    # Update the message content
    # If we have mixed content (text + images), we must use the list format
    # If we only have text parts, we could join them, but list format is safer for multimodal models
    if content_parts:
        last_msg["content"] = content_parts

    return messages


@router.post("/chat/completions")
async def chat_completions(request: ChatRequest, agents_registry: Dict = Depends(get_agents_registry)):
    """
    OpenAI-compatible chat endpoint.
    Supports:
    - Streaming (stream=True) with XML status tags.
    - Non-streaming (stream=False).
    - File processing (via 'files' field).
    """
    try:
        # 1. Validation
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        if request.model not in agents_registry:
            raise HTTPException(status_code=404, detail=f"Model '{request.model}' not found")

        # 2. File Processing
        messages = await _process_files(request.files, request.messages)

        # 3. Setup
        user_query = messages[-1].get("content", "")
        agent_info = agents_registry[request.model]
        session_id = request.session_id or f"session_{uuid.uuid4().hex[:8]}"
        user_id = request.user or "default_user"
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        current_timestamp = int(time.time())

        # 4. Streaming Response
        if request.stream:

            async def generate_stream():
                # Initial chunk
                initial = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": current_timestamp,
                    "model": request.model,
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(initial)}\n\n"

                # Agent stream
                async for chunk in stream_agent(
                    agent_info, user_query, user_id, session_id, completion_id, current_timestamp, request.model, verbose=True
                ):
                    yield chunk

                # Final chunk
                final = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": current_timestamp,
                    "model": request.model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(final)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        # 5. Non-streaming Response
        response_text = await call_agent_async(
            query=user_query,
            session_id=session_id,
            model_id=request.model,
            agents_registry=agents_registry,
        )

        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": current_timestamp,
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,  # Token counting for multimodal/lists is complex, skipping for now
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(response_text.split()),
            },
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
