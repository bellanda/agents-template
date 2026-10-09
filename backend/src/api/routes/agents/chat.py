import base64
import mimetypes
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from asyncpg.connection import Connection
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.core.logging import get_logger
from api.services.agents.executors import call_agent_async
from api.services.agents.registry import get_agents_registry
from api.services.agents.streaming import sse_error_chunk, stream_agent
from api.services.agents.utils import convert_file_to_text
from api.services.auth import get_auth_context
from config.api import api_config
from config.database import get_conn

router = APIRouter()
log = get_logger(__name__)


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]
    model: str
    stream: bool = False
    session_id: str | None = None
    files: list[str] | None = None  # Optional list of file paths to process
    active_client_id: str | None = None


async def _process_files(
    files: list[str] | None, messages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
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
                content_parts.append(
                    {"type": "text", "text": f"\n[Error processing image {file_path}: {e}]\n"}
                )

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


def _resolve_local_upload(url: str) -> Path | None:
    """If ``url`` points at our /uploads mount, return the on-disk Path; else None.

    Aceita layout flat antigo (``/api/v1/uploads/<hash>.ext``) e novo layout
    escopado (``/api/v1/uploads/<user_id>/<thread_id>/<hash>.ext``). Cada
    componente é sanitizado e o resultado final precisa estar contido em
    ``UPLOADS_DIR.resolve()``.
    """
    if not url:
        return None
    parsed = urlparse(url)
    path = parsed.path or url
    prefix = api_config.UPLOADS_HTTP_PREFIX
    if not path.startswith(prefix + "/"):
        return None
    raw_relative = path[len(prefix) + 1 :]
    if not raw_relative:
        return None
    safe_segments: list[str] = []
    for segment in raw_relative.split("/"):
        if not segment:
            continue
        cleaned = Path(segment).name
        if not cleaned or cleaned in ("..", "."):
            return None
        safe_segments.append(cleaned)
    if not safe_segments:
        return None
    base = api_config.UPLOADS_DIR.resolve()
    target = (api_config.UPLOADS_DIR.joinpath(*safe_segments)).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return None
    if not target.is_file():
        return None
    return target


def _document_to_text(path: Path) -> str:
    return convert_file_to_text(str(path)) or ""


def _data_url_to_text(url: str, media_type: str) -> str:
    """Decodifica um data URL e converte para texto via MarkItDown (PDF/DOCX/etc)."""
    if not url.startswith("data:"):
        return ""
    header, _, encoded = url.partition(",")
    if ";base64" not in header or not encoded:
        return ""
    try:
        raw = base64.b64decode(encoded)
    except Exception:
        return ""
    ext = mimetypes.guess_extension(media_type) or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as fp:
        fp.write(raw)
        tmp_path = fp.name
    try:
        return convert_file_to_text(tmp_path) or ""
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            log.warning("temp_file_delete_failed", path=tmp_path)


def _file_to_data_url(path: Path, media_type: str) -> str:
    """Read a local upload from disk and return it as a base64 data URL."""
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{media_type};base64,{encoded}"


def _extract_user_visible_text(messages: list[dict[str, Any]]) -> str:
    """User-typed text only — no document extractions.

    Used as the visible content for the persisted user message. Document
    content extracted from PDF/DOCX is sent to the LLM (via
    ``_extract_user_content``) but must NOT pollute the user's chat bubble;
    the attachment card already communicates the upload.
    """
    if not messages:
        return ""
    user_messages = [m for m in messages if m.get("role") == "user"]
    last_msg = user_messages[-1] if user_messages else messages[-1]
    parts = last_msg.get("parts")
    if isinstance(parts, list):
        chunks: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and part.get("text"):
                chunks.append(str(part["text"]))
        return " ".join(c for c in chunks if c).strip()
    content = last_msg.get("content") or last_msg.get("text") or ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return str(content.get("text") or "")
    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                chunks.append(str(part.get("text") or ""))
        return " ".join(c for c in chunks if c).strip()
    return ""


def _extract_user_file_parts(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """File parts saneados (sem base64) prontos para persistir no histórico."""
    if not messages:
        return []
    user_messages = [m for m in messages if m.get("role") == "user"]
    last_msg = user_messages[-1] if user_messages else messages[-1]
    parts = last_msg.get("parts")
    if not isinstance(parts, list):
        return []

    out: list[dict[str, Any]] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        if part.get("type") not in {"file", "image"}:
            continue
        url = (
            part.get("url")
            or (part.get("image_url") or {}).get("url")
            or (part.get("image") or {}).get("url")
            or ""
        )
        media_type = part.get("mediaType") or part.get("media_type") or part.get("mimeType") or ""
        if url.startswith("data:"):
            continue
        filename = part.get("filename") or part.get("name") or ""
        out.append(
            {
                "type": "file",
                "url": url,
                "mediaType": media_type,
                "filename": filename,
            }
        )
    return out


def _extract_user_content(messages: list[dict[str, Any]]) -> str | list[dict[str, Any]]:
    """Extrai o conteúdo da última mensagem do usuário no formato consumível pelo LLM.

    Suporta:
    - Vercel AI SDK V5: ``parts: [{type:'text'|'file', ...}]``. Imagens viram
      ``image_url`` (multimodal); documentos viram texto via MarkItDown.
    - OpenAI clássico: ``content: str | list``.

    Retorna ``str`` simples quando só há texto e ``list[dict]`` multimodal quando
    há ao menos uma imagem (formato compatível com ChatOpenAI/ChatGoogle/etc).
    """
    if not messages:
        return ""

    user_messages = [m for m in messages if m.get("role") == "user"]
    last_msg = user_messages[-1] if user_messages else messages[-1]

    parts = last_msg.get("parts")
    if isinstance(parts, list):
        text_chunks: list[str] = []
        image_parts: list[dict[str, Any]] = []
        document_chunks: list[str] = []

        for part in parts:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "text":
                if part.get("text"):
                    text_chunks.append(str(part["text"]))
            elif ptype in {"file", "image"}:
                url = (
                    part.get("url")
                    or (part.get("image_url") or {}).get("url")
                    or (part.get("image") or {}).get("url")
                    or ""
                )
                media_type = (
                    part.get("mediaType") or part.get("media_type") or part.get("mimeType") or ""
                )
                if not url:
                    continue
                local_path = _resolve_local_upload(url)
                if media_type.startswith("image/") or ptype == "image":
                    if local_path is not None:
                        effective_media = media_type or (
                            mimetypes.guess_type(local_path.name)[0] or "image/jpeg"
                        )
                        image_url_value = _file_to_data_url(local_path, effective_media)
                    else:
                        image_url_value = url
                    image_parts.append({"type": "image_url", "image_url": {"url": image_url_value}})
                else:
                    if local_path is not None:
                        text = _document_to_text(local_path)
                    else:
                        text = _data_url_to_text(url, media_type)
                    if text:
                        filename = part.get("filename") or part.get("name") or "arquivo"
                        document_chunks.append(
                            f"\n\n--- Conteúdo do arquivo {filename} ---\n{text}\n-----------------------------------\n"
                        )

        combined_text = " ".join(c for c in text_chunks if c).strip() + "".join(document_chunks)

        if image_parts:
            multimodal: list[dict[str, Any]] = []
            if combined_text:
                multimodal.append({"type": "text", "text": combined_text})
            multimodal.extend(image_parts)
            return multimodal
        return combined_text

    content = last_msg.get("content") or last_msg.get("text") or ""

    if isinstance(content, str):
        return content

    if isinstance(content, dict):
        return content.get("text", "")

    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and (
                part.get("type") == "text" or ("text" in part and part.get("type") is None)
            ):
                texts.append(part.get("text", ""))
        return " ".join(texts).strip()

    return ""


@router.post("/chat/completions")
async def chat_completions(
    request: ChatRequest,
    ctx: dict = Depends(get_auth_context),
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
        # `request.files` é caminho legado (server-side paths). O Vercel AI SDK V5
        # entrega arquivos dentro das `parts` da última user message, então
        # `_extract_user_content` cuida do caso multimodal moderno.
        messages = await _process_files(request.files, request.messages)

        # 3. Setup
        user_query = _extract_user_content(messages)
        user_file_parts = _extract_user_file_parts(messages)
        user_visible_text = _extract_user_visible_text(messages)
        if not user_query and not user_file_parts:
            raise HTTPException(status_code=400, detail="No user query found")

        # Defesa em profundidade: se o modelo não suporta imagem mas o cliente
        # enviou parts image_url assim mesmo, retornamos 400 antes de gastar
        # uma request com erro confuso do provider.
        agent_caps = agents_registry[request.model].get("capabilities") or {}
        if (
            isinstance(user_query, list)
            and any(p.get("type") == "image_url" for p in user_query)
            and not agent_caps.get("image_input")
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Model '{request.model}' não aceita imagens. "
                    "Escolha um modelo com suporte multimodal ou remova os anexos."
                ),
            )

        agent_info = agents_registry[request.model]
        session_id = request.session_id or f"session_{uuid.uuid4().hex[:8]}"
        # Identity comes from the auth seam (header/token), never the request body.
        user_id = ctx["user_id"]
        active_client_id = ctx["client_id"] or request.active_client_id
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        current_timestamp = int(time.time())

        log.info(
            "chat_completions",
            model=request.model,
            session_id=session_id,
            agent_name=agent_info.get("name"),
        )
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
                        active_client_id=active_client_id,
                        tenant_id=ctx["tenant_id"],
                        user_file_parts=user_file_parts,
                        user_visible_text=user_visible_text,
                    ):
                        yield chunk
                except Exception as e:
                    log.exception(
                        "chat_stream_iteration_failed",
                        session_id=session_id,
                        model=request.model,
                    )
                    yield sse_error_chunk(f"Stream interrupted: {e!s}")
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    # `no-transform`: sem ele a Cloudflare comprime/bufferiza o text/event-stream e
                    # nada chega ao browser até a conexão cair (~125s) — Kailos prod 2026-10-09.
                    "Cache-Control": "no-cache, no-transform",
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
            user_id=user_id,
            client_id=active_client_id,
            tenant_id=ctx["tenant_id"],
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
