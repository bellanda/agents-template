import base64
import mimetypes
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import anyio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.core.agents.ai_budget import (
    AiBudgetExceededError,
    budget_http_exception,
    ensure_within_budget,
)
from api.core.logging import get_logger
from api.models.agents.history import ChatHistoryThread
from api.repositories.agents.chat_history import get_chat_messages, get_chat_owner, save_chat
from api.services.agents.executors import call_agent_async
from api.services.agents.registry import get_agents_registry
from api.services.agents.streaming import PREVIEW_LENGTH, sse_error_chunk, stream_agent
from api.services.agents.utils import convert_file_to_text
from api.services.auth import get_auth_context
from api.services.uploads.upload_access_service import resolve_authorized_upload
from config.api import api_config
from config.database import ConnScope, get_conn_scope

router = APIRouter()
log = get_logger(__name__)


class ChatRequest(BaseModel):
    """Chat body. NEVER carries identity or server paths (audit 2026-11-13 skills-backend-01).

    The legacy ``files: list[str]`` field (server-side paths the endpoint opened and fed to the
    model) was removed: any logged-in user could point it at ``/proc/self/environ`` or a config
    file and read it back through the conversation. Attachments arrive as ``parts`` of the last
    user message (Vercel AI SDK v5) and may only reference ``/uploads/...`` URLs the caller owns
    (``upload_access_service``). Unknown fields such as ``files`` or ``user`` are ignored.
    """

    messages: list[dict[str, Any]]
    model: str
    stream: bool = False
    session_id: str | None = None
    active_client_id: str | None = None


async def _claim_thread_turn(
    scope: ConnScope,
    *,
    session_id: str,
    user_id: str,
    agent_id: str,
    user_text: str,
    assistant_text: str,
) -> None:
    """Persist a non-streaming turn so the thread has an OWNER row in `chat_history`.

    Streaming saves its own turn (`stream_agent`); this path did not, so `get_chat_owner` stayed
    None and any other user who knew the `session_id` resumed the checkpoint (the victim's
    context). Same preview rule as streaming (audit 2026-11 r2-kailos-be-portals-messaging-01).
    """
    async with scope() as db:
        history = list(await get_chat_messages(db, session_id) or [])
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": assistant_text})
        preview = user_text or assistant_text
        await save_chat(
            db,
            ChatHistoryThread(
                thread_id=session_id,
                user_id=user_id,
                agent_id=agent_id,
                messages=history,
                preview=(preview[:PREVIEW_LENGTH] + "...")
                if len(preview) > PREVIEW_LENGTH
                else (preview or None),
            ),
        )


def _document_to_text(path: Path) -> str:
    return convert_file_to_text(str(path)) or ""


def _data_url_to_text(url: str, media_type: str) -> str:
    """Decodifica um data URL e converte para texto via MarkItDown (PDF/DOCX/etc).

    Blocking (decode + temp file + MarkItDown): callers run it with ``anyio.to_thread``.
    """
    if not url.startswith("data:"):
        return ""
    header, _, encoded = url.partition(",")
    if ";base64" not in header or not encoded:
        return ""
    # Same ceiling as a real upload: an inline data URL otherwise bypasses the size gate of
    # routes/uploads.py and forces an unbounded decode + MarkItDown parse (DoS).
    max_encoded = (api_config.AI_ATTACHMENT_MAX_BYTES // 3 + 1) * 4
    if len(encoded) > max_encoded:
        log.warning("data_url_document_oversize", encoded_len=len(encoded), limit=max_encoded)
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
    """Read a local upload from disk and return it as a base64 data URL (blocking: to_thread)."""
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


async def _extract_user_content(
    messages: list[dict[str, Any]], scope: ConnScope, owner_user_id: str
) -> str | list[dict[str, Any]]:
    """Extrai o conteúdo da última mensagem do usuário no formato consumível pelo LLM.

    Suporta:
    - Vercel AI SDK V5: ``parts: [{type:'text'|'file', ...}]``. Imagens viram
      ``image_url`` (multimodal); documentos viram texto via MarkItDown.
    - OpenAI clássico: ``content: str | list``.

    Retorna ``str`` simples quando só há texto e ``list[dict]`` multimodal quando
    há ao menos uma imagem (formato compatível com ChatOpenAI/ChatGoogle/etc).

    Attachment URLs are authorised against ``user_uploads`` (own or public only) inside a SHORT
    ``scope()`` phase; the file read / MarkItDown conversion then runs in a worker thread so a
    large PDF never blocks the event loop (audit 2026-11-13 core-ai-08).
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
                local_path: Path | None = None
                if not url.startswith("data:"):
                    async with scope() as db:
                        local_path = await resolve_authorized_upload(db, url, owner_user_id)
                if local_path is not None:
                    stored_size = (await anyio.Path(local_path).stat()).st_size
                    if stored_size > api_config.AI_ATTACHMENT_MAX_BYTES:
                        # Stored fine (uploads go up to FILE_MAX_BYTES), never read whole into RAM.
                        limit_mb = api_config.AI_ATTACHMENT_MAX_BYTES // (1024 * 1024)
                        filename = part.get("filename") or part.get("name") or local_path.name
                        document_chunks.append(
                            f'\n\n[O arquivo "{filename}" foi enviado, mas é grande demais para '
                            f"a IA ler (máximo de {limit_mb} MB para leitura). Envie uma versão "
                            "menor ou só as páginas necessárias.]\n"
                        )
                        continue
                if media_type.startswith("image/") or ptype == "image":
                    if local_path is not None:
                        effective_media = media_type or (
                            mimetypes.guess_type(local_path.name)[0] or "image/jpeg"
                        )
                        image_url_value = await anyio.to_thread.run_sync(
                            _file_to_data_url, local_path, effective_media
                        )
                    else:
                        image_url_value = url
                    image_parts.append({"type": "image_url", "image_url": {"url": image_url_value}})
                else:
                    if local_path is not None:
                        text = await anyio.to_thread.run_sync(_document_to_text, local_path)
                    else:
                        text = await anyio.to_thread.run_sync(_data_url_to_text, url, media_type)
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
    scope: ConnScope = Depends(get_conn_scope),
):
    """
    OpenAI-compatible chat endpoint.
    Supports:
    - Streaming (stream=True) with XML status tags.
    - Non-streaming (stream=False).
    - Attachments via the ``parts`` of the last user message (own ``/uploads`` URLs only).

    No ``Depends(get_conn)`` here on purpose: a yield-dependency stays open until the whole
    StreamingResponse is sent, pinning 1 of ``max_size`` pool connections per running answer
    (audit 2026-11-13 core-performance-01). Each DB phase borrows one through ``scope()``.
    """
    try:
        # 1. Validation
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        if request.model not in agents_registry:
            raise HTTPException(status_code=404, detail=f"Model '{request.model}' not found")

        agent_info = agents_registry[request.model]
        session_id = request.session_id or f"session_{uuid.uuid4().hex[:8]}"
        # Identity comes from the auth seam (header/token), never the request body.
        user_id = ctx["user_id"]
        tenant_id = ctx["tenant_id"]

        # 2. Thread ownership + spend cap, BEFORE any file work or model call. `session_id` is
        # client-supplied and the LangGraph checkpoint is keyed by thread_id alone: without the
        # owner check a foreign id resumes the victim's context and `save_chat` overwrites their
        # history (audit 2026-11-13 core-ai-02).
        async with scope() as db:
            owner = await get_chat_owner(db, session_id)
            if owner is not None and owner[0] != user_id:
                raise HTTPException(status_code=403, detail="Not allowed to use this thread")
            try:
                await ensure_within_budget(db, tenant_id)
            except AiBudgetExceededError:
                raise budget_http_exception() from None

        # 3. Setup (attachments come from `parts`; see ChatRequest)
        user_query = await _extract_user_content(request.messages, scope, user_id)
        user_file_parts = _extract_user_file_parts(request.messages)
        user_visible_text = _extract_user_visible_text(request.messages)
        if not user_query and not user_file_parts:
            raise HTTPException(status_code=400, detail="No user query found")

        # Defesa em profundidade: se o modelo não suporta imagem mas o cliente
        # enviou parts image_url assim mesmo, retornamos 400 antes de gastar
        # uma request com erro confuso do provider.
        agent_caps = agent_info.get("capabilities") or {}
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
                        active_client_id=active_client_id,
                        tenant_id=ctx["tenant_id"],
                        user_file_parts=user_file_parts,
                        user_visible_text=user_visible_text,
                    ):
                        yield chunk
                except Exception:
                    log.exception(
                        "chat_stream_iteration_failed",
                        session_id=session_id,
                        model=request.model,
                    )
                    yield sse_error_chunk("A resposta foi interrompida. Tente novamente.")
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
        await _claim_thread_turn(
            scope,
            session_id=session_id,
            user_id=user_id,
            agent_id=request.model,
            user_text=user_visible_text,
            assistant_text=response_text,
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
    except Exception:
        # Never leak internal exception text (SQL fragments, upstream API errors, paths):
        # the traceback goes to the log, the client gets a generic message.
        log.exception("chat_completions_unhandled_error")
        raise HTTPException(status_code=500, detail="Internal error") from None
