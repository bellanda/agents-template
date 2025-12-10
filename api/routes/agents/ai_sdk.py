import json
import time
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.services.agents.executors import call_agent_async
from api.services.agents.registry import get_agents_registry
from api.services.agents.streaming import stream_ai_sdk_agent

router = APIRouter(prefix="/ui")


class UIMessagePart(BaseModel):
    """Minimal UIMessage part format supported by the AI SDK UI."""

    type: str = Field(..., description="Part type, e.g. 'text'")
    text: Optional[str] = None


class UIMessage(BaseModel):
    """UIMessage-compatible payload expected by Vercel AI SDK UI."""

    id: Optional[str] = None
    role: str
    content: Optional[str] = None
    parts: Optional[List[UIMessagePart]] = None


class AISDKChatRequest(BaseModel):
    messages: List[UIMessage]
    model: str
    stream: bool = True
    session_id: Optional[str] = None
    user: Optional[str] = None
    verbose: bool = False


def _extract_ui_message_text(message: UIMessage) -> str:
    """Extract plain text from a UIMessage (parts preferred, fallback to content)."""
    if message.parts:
        texts = []
        for part in message.parts:
            if part.type in {"text", "reasoning"} and part.text:
                texts.append(part.text)
        if texts:
            return " ".join(texts).strip()
    return (message.content or "").strip()


def _sse(payload: Dict) -> str:
    """Serialize payload as SSE data line."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def ai_sdk_chat_endpoint(
    request: AISDKChatRequest = Body(...),
    agents_registry: Dict = Depends(get_agents_registry),
):
    """
    AI SDK UI-compatible endpoint.

    - Accepts UIMessage format used by Vercel AI Elements / @ai-sdk/react.
    - Returns SSE stream compatível com Vercel AI Elements (@ai-sdk/react) ou uma única
      resposta quando stream=False.
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    requested_model = request.model
    if requested_model not in agents_registry:
        available = list(agents_registry.keys())
        raise HTTPException(status_code=404, detail=f"Model '{requested_model}' not found. Available: {available}")

    user_query = _extract_ui_message_text(request.messages[-1])
    session_id = request.session_id or f"ui_session_{requested_model}"
    # user_id = request.user or "ui_user"
    current_timestamp = int(time.time())
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"

    if not user_query:
        raise HTTPException(status_code=400, detail="Last message must contain text")

    if request.stream:

        async def generate_stream():
            # text-start: inicia a resposta
            yield _sse({"type": "text-start", "id": completion_id})

            async for chunk in stream_ai_sdk_agent(
                agents_registry[requested_model],
                user_query,
                session_id,
            ):
                if not chunk:
                    continue
                # text-delta: envia pequenos pedaços de texto
                yield _sse({"type": "text-delta", "id": completion_id, "delta": chunk})

            # text-end: fecha a resposta
            yield _sse({"type": "text-end", "id": completion_id})

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Transfer-Encoding": "chunked",
            },
        )

    # Non-streaming fallback
    assistant_response = await call_agent_async(
        query=user_query,
        session_id=session_id,
        model_id=requested_model,
        agents_registry=agents_registry,
    )

    message_payload = {
        "id": completion_id,
        "role": "assistant",
        "parts": [{"type": "text", "text": assistant_response}],
    }

    return {
        "id": completion_id,
        "object": "chat.ui.completion",
        "created": current_timestamp,
        "model": requested_model,
        "message": message_payload,
    }
