import base64
import mimetypes
import time
import uuid
from traceback import format_exc
from typing import Any

from asyncpg.connection import Connection
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.services.agents.executors import call_agent_async
from api.services.agents.registry import get_agents_registry
from api.services.agents.streaming import sse_error_chunk, stream_agent
from api.services.agents.utils import convert_file_to_text
from config.database import get_conn

router = APIRouter()


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]
    model: str
    stream: bool = False
    session_id: str | None = None
    user: str | None = None
    files: list[str] | None = None  # Optional list of file paths to process
    realtor_id: int | None = None
    active_client_id: str | None = None


async def _process_files(files: list[str] | None, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
                    content_parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{encoded_string}"},
                        }
                    )
            except Exception as e:
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


def _extract_user_query(messages: list[dict[str, Any]]) -> str:
    """Extrai o texto da última mensagem do usuário, suportando múltiplos formatos (OpenAI, Vercel AI SDK parts, etc)."""
    if not messages:
        return ""

    user_messages = [m for m in messages if m.get("role") == "user"]
    last_msg = messages[-1] if not user_messages else user_messages[-1]

    parts = last_msg.get("parts")
    if isinstance(parts, list):
        texts = []
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
        return " ".join(texts).strip()

    content = last_msg.get("content") or last_msg.get("text") or ""

    if isinstance(content, str):
        return content

    if isinstance(content, dict):
        return content.get("text", "")

    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and (part.get("type") == "text" or ("text" in part and part.get("type") is None)):
                texts.append(part.get("text", ""))
        return " ".join(texts).strip()

    return ""


@router.post("/chat/completions")
async def chat_completions(
    request: ChatRequest,
    agents_registry: dict = Depends(get_agents_registry),
    conn: Connection = Depends(get_conn),
):
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
        user_query = _extract_user_query(messages)
        if not user_query:
            raise HTTPException(status_code=400, detail="No user query found")

        agent_info = agents_registry[request.model]
        session_id = request.session_id or f"session_{uuid.uuid4().hex[:8]}"
        user_id = request.user or "default_user"
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        current_timestamp = int(time.time())

        print(f"[chat_completions] model={request.model!r} session_id={session_id!r} agent_name={agent_info.get('name')!r}")
        # 4. Streaming Response
        if request.stream:

            async def generate_stream():
                try:
                    async for chunk in stream_agent(
                        agent_info,
                        user_query,
                        user_id,
                        session_id,
                        completion_id,
                        current_timestamp,
                        request.model,
                        conn=conn,
                        realtor_id=request.realtor_id,
                        active_client_id=request.active_client_id,
                    ):
                        yield chunk
                except Exception as e:
                    print(f"[chat_completions] stream iteration failed session_id={session_id!r} model={request.model!r}\n{format_exc()}")
                    yield sse_error_chunk(f"Stream interrupted: {e!s}")
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "x-vercel-ai-ui-message-stream": "v1",
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
