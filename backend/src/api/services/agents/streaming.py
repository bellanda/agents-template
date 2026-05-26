import asyncio
import contextlib
import os
from collections.abc import AsyncGenerator
from typing import Any

import orjson
from asyncpg.connection import Connection

from api.core.agents.callbacks import usage_recorder
from api.core.logging import get_logger
from api.models.agents.history import ChatHistoryThread
from api.repositories.agents.chat_history import get_chat_messages, save_chat
from api.repositories.agents.usage import build_usage_from_ai_message
from api.services.agents.executors import (
    extract_thinking_from_content,
    normalize_chunk_text,
    reasoning_from_additional_kwargs,
)
from config.database import get_pool

log = get_logger(__name__)

# Strong references to detached save tasks. Without this set, the GC may
# collect the Task before it runs — classic asyncio.create_task pitfall.
_DETACHED_TASKS: set[asyncio.Task] = set()


def _spawn_detached(coro) -> asyncio.Task:
    """Fire-and-forget task that survives the current task's cancellation
    AND keeps a strong reference so the GC can't drop it before completion."""
    task = asyncio.create_task(coro)
    _DETACHED_TASKS.add(task)
    task.add_done_callback(_DETACHED_TASKS.discard)
    return task


PREVIEW_LENGTH = 200


def _agent_stream_debug() -> bool:
    return os.environ.get("AGENT_STREAM_DEBUG", "1").strip().lower() not in ("0", "false", "no")


def _dev_preview(val: Any, max_len: int = 900) -> str:
    try:
        s = val if isinstance(val, str) else repr(val)
    except Exception:
        s = "<unreprable>"
    if len(s) > max_len:
        return f"{s[:max_len]}... [truncated, total {len(s)} chars]"
    return s


def _chunk(type_name: str, message_id: str, delta: str = "") -> str:
    """Build SSE chunk for Vercel AI SDK useChat (text/event-stream format)."""
    payload: dict = {"type": type_name, "id": message_id}
    if delta:
        payload["delta"] = delta
    return f"data: {orjson.dumps(payload).decode('utf-8')}\n\n"


async def _safe_get_chat_messages(conn: Connection, session_id: str) -> list[dict] | None:
    """Wrapper para get_chat_messages que swallow falhas — usado em finally após
    cancel, onde queremos prosseguir mesmo se a leitura prévia falhar."""
    try:
        return await get_chat_messages(conn, session_id)
    except Exception:
        log.exception("safe_get_chat_messages_failed", session_id=session_id)
        return None


def _tool_input_chunk(tool_call_id: str, tool_name: str, tool_input: Any) -> str:
    """Vercel AI SDK Data Stream: dynamic tool input is now available.

    Frontend receives this as a part with state='input-available'.
    """
    payload = {
        "type": "tool-input-available",
        "toolCallId": tool_call_id,
        "toolName": tool_name,
        "input": tool_input,
        "dynamic": True,
    }
    return f"data: {orjson.dumps(payload).decode('utf-8')}\n\n"


def _tool_output_chunk(tool_call_id: str, output: Any) -> str:
    """Vercel AI SDK Data Stream: tool output is available.

    For our protocol, output is an envelope `{type, data}` so the frontend
    registry can pick the right JSX renderer.
    """
    payload = {
        "type": "tool-output-available",
        "toolCallId": tool_call_id,
        "output": output,
    }
    return f"data: {orjson.dumps(payload).decode('utf-8')}\n\n"


def _tool_error_chunk(tool_call_id: str, error_text: str) -> str:
    payload = {
        "type": "tool-output-error",
        "toolCallId": tool_call_id,
        "errorText": error_text,
    }
    return f"data: {orjson.dumps(payload).decode('utf-8')}\n\n"


def _error_chunk(error_text: str) -> str:
    payload = {"type": "error", "errorText": error_text}
    return f"data: {orjson.dumps(payload).decode('utf-8')}\n\n"


def sse_error_chunk(error_text: str) -> str:
    """Same as stream-internal error event; exposed for route-level fallbacks."""
    return _error_chunk(error_text)


def _reasoning_from_ai_message(msg: Any) -> str:
    """Full reasoning/thinking string from a finished AIMessage (e.g. Gemini on_chat_model_end)."""
    if msg is None:
        return ""
    add = getattr(msg, "additional_kwargs", None) or {}
    return extract_thinking_from_content(
        getattr(msg, "content", None)
    ) + reasoning_from_additional_kwargs(add)


async def stream_agent(
    agent_info: dict,
    query: "str | list[dict[str, Any]]",
    user_id: str,
    session_id: str,
    completion_id: str,
    current_timestamp: int,
    requested_model: str,
    conn: Connection | None,
    realtor_id: int | None = None,
    active_client_id: str | None = None,
    user_file_parts: list[dict[str, Any]] | None = None,
    user_visible_text: str | None = None,
) -> AsyncGenerator[str]:
    """Stream agent events - Vercel AI SDK Data Stream Protocol (SSE).

    `query` aceita ``str`` (texto puro) ou multimodal ``list[dict]`` no formato
    OpenAI parts (``[{type:'text', text}, {type:'image_url', image_url}]``) —
    necessário para suportar imagens anexadas via Vercel AI SDK no front.
    """
    agent = agent_info["agent"]
    save_to_db: bool = agent_info.get("save_to_db", True)

    if isinstance(query, str):
        query_text_for_log = query
    else:
        text_chunks = [
            p.get("text", "") for p in query if isinstance(p, dict) and p.get("type") == "text"
        ]
        query_text_for_log = " ".join(text_chunks).strip()

    # Visible history: only the text the user typed, never the document
    # extractions. Attachments are shown as cards via user_file_parts;
    # duplicating extracted content into the user bubble would be noise.
    has_files = bool(user_file_parts)
    if user_visible_text is not None:
        query_text_for_history = user_visible_text
    else:
        query_text_for_history = query_text_for_log
    if not query_text_for_history and has_files:
        query_text_for_history = ""

    log.info(
        "stream_agent_start",
        model=requested_model,
        agent_type=type(agent).__name__,
        session_id=session_id,
        query_len=len(query_text_for_log),
        multimodal=not isinstance(query, str),
    )
    yield f"data: {orjson.dumps({'type': 'start', 'messageId': completion_id}).decode('utf-8')}\n\n"

    reasoning_started = False
    text_started = False
    stream_failed = False
    was_cancelled = False
    full_response = ""
    full_reasoning = ""
    tool_parts_by_call_id: dict[str, dict[str, Any]] = {}
    # ordered_parts é a single source of truth para a ordem em que o modelo
    # emitiu cada bloco — texto, reasoning e tool calls aparecem na sequência
    # real, não num esquema fixo (reasoning→tools→text). Isso garante que a UI
    # renderize "texto curto, tool, texto resposta" corretamente quando o
    # modelo intercala chamadas de ferramenta entre parágrafos.
    ordered_parts: list[dict[str, Any]] = []
    last_ai_message: Any | None = None

    def append_text_part(content: str) -> None:
        if not ordered_parts or ordered_parts[-1].get("type") != "text":
            ordered_parts.append({"type": "text", "text": content})
        else:
            ordered_parts[-1]["text"] = (ordered_parts[-1].get("text") or "") + content

    def append_reasoning_part(content: str) -> None:
        if not ordered_parts or ordered_parts[-1].get("type") != "reasoning":
            ordered_parts.append({"type": "reasoning", "reasoning": content})
        else:
            ordered_parts[-1]["reasoning"] = (ordered_parts[-1].get("reasoning") or "") + content

    langgraph_config: dict = {
        "configurable": {
            "thread_id": session_id,
            "realtor_id": realtor_id,
            "active_client_id": active_client_id,
        },
        # UsageRecorderCallback reads these to persist agent_message_usage.
        "metadata": {
            "thread_id": session_id,
            "agent_id": requested_model,
            "user_id": user_id,
            "client_id": active_client_id,
        },
        # astream_events doesn't propagate callbacks attached via .with_config() —
        # pass the recorder explicitly so on_chat_model_start/end fire on every LLM call.
        "callbacks": [usage_recorder],
    }

    _stream_chunk_i = 0
    _stream_chars = 0

    try:
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": query}]},
            version="v1",
            config=langgraph_config,
        ):
            event_type = event.get("event") or ""
            ev_name = event.get("name") or ""
            ev_run = str(event.get("run_id", ""))[:10]
            data = event.get("data") or {}
            err = data.get("error")

            if _agent_stream_debug():
                if event_type == "on_chat_model_stream":
                    _stream_chunk_i += 1
                    chunk = data.get("chunk")
                    if chunk is not None:
                        dc = len(normalize_chunk_text(getattr(chunk, "content", None)))
                    else:
                        dc = 0
                    _stream_chars += dc
                    if _stream_chunk_i == 1 or _stream_chunk_i % 40 == 0:
                        log.debug(
                            "stream_chunk",
                            i=_stream_chunk_i,
                            run=ev_run,
                            name=ev_name,
                            delta_chars=dc,
                            total_chars=_stream_chars,
                        )
                elif event_type in ("on_tool_start", "on_tool_end", "on_tool_error"):
                    log.debug(
                        "stream_tool_event",
                        event=event_type,
                        run=ev_run,
                        name=ev_name,
                        input=_dev_preview(data.get("input"), 600),
                    )
                    if event_type in ("on_tool_end", "on_tool_error"):
                        log.debug(
                            "stream_tool_output",
                            event=event_type,
                            output=_dev_preview(data.get("output"), 800),
                        )
                    if event_type == "on_tool_error" or err is not None:
                        log.debug("stream_tool_error", event=event_type, err=repr(err))
                elif event_type.startswith("on_chain") or event_type.startswith("on_chat_model"):
                    log.debug(
                        "stream_event",
                        event=event_type,
                        run=ev_run,
                        name=ev_name,
                        data_keys=list(data.keys()),
                    )
                    if err is not None:
                        log.debug("stream_event_nested_error", err=repr(err))
                else:
                    log.debug(
                        "stream_event",
                        event=event_type,
                        run=ev_run,
                        name=ev_name,
                        data_keys=list(data.keys()),
                    )
                    if err is not None:
                        log.debug("stream_event_error_field", err=repr(err))

            if event_type == "on_tool_start":
                tool_call_id = str(event.get("run_id") or "")
                tool_input = data.get("input")
                if tool_call_id and ev_name:
                    if tool_call_id not in tool_parts_by_call_id:
                        new_part: dict[str, Any] = {
                            "type": "dynamic-tool",
                            "toolName": ev_name,
                            "toolCallId": tool_call_id,
                            "state": "input-available",
                            "input": tool_input,
                        }
                        tool_parts_by_call_id[tool_call_id] = new_part
                        ordered_parts.append(new_part)
                    else:
                        tool_parts_by_call_id[tool_call_id].update(
                            {
                                "toolName": ev_name,
                                "state": "input-available",
                                "input": tool_input,
                            }
                        )
                    yield _tool_input_chunk(tool_call_id, ev_name, tool_input)
                continue

            if event_type == "on_tool_end":
                tool_call_id = str(event.get("run_id") or "")
                if tool_call_id:
                    output = data.get("output")
                    raw = getattr(output, "content", None) if output is not None else None
                    if raw is None:
                        raw = output
                    if isinstance(raw, str):
                        with contextlib.suppress(orjson.JSONDecodeError):
                            raw = orjson.loads(raw)
                    # Tools com response_format="content_and_artifact" retornam
                    # (content, artifact) onde `content` é o envelope LLM-only e
                    # `artifact` carrega o ui_data (image_urls, scores etc.) que o
                    # frontend precisa para renderizar os cards. Sem esse merge,
                    # ChatListingCard cai no PLACEHOLDER_IMAGE.
                    artifact = getattr(output, "artifact", None) if output is not None else None
                    if isinstance(raw, dict) and isinstance(artifact, dict):
                        raw = {**raw, "ui_data": artifact}
                    part = tool_parts_by_call_id.get(tool_call_id)
                    if part is None:
                        part = {
                            "type": "dynamic-tool",
                            "toolName": ev_name or "",
                            "toolCallId": tool_call_id,
                            "input": data.get("input"),
                        }
                        tool_parts_by_call_id[tool_call_id] = part
                        ordered_parts.append(part)
                    part["state"] = "output-available"
                    part["output"] = raw
                    yield _tool_output_chunk(tool_call_id, raw)
                continue

            if event_type == "on_tool_error":
                tool_call_id = str(event.get("run_id") or "")
                if tool_call_id:
                    error_message = str(err or "Tool failed")
                    part = tool_parts_by_call_id.get(tool_call_id)
                    if part is None:
                        part = {
                            "type": "dynamic-tool",
                            "toolName": ev_name or "",
                            "toolCallId": tool_call_id,
                            "input": data.get("input"),
                        }
                        tool_parts_by_call_id[tool_call_id] = part
                        ordered_parts.append(part)
                    part["state"] = "output-error"
                    part["errorText"] = error_message
                    yield _tool_error_chunk(tool_call_id, error_message)
                continue

            if event_type == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk is None:
                    continue
                raw_content = getattr(chunk, "content", None)
                gemini_thinking = extract_thinking_from_content(raw_content)
                content = normalize_chunk_text(raw_content)
                additional = getattr(chunk, "additional_kwargs", None) or {}
                reasoning_content = gemini_thinking + reasoning_from_additional_kwargs(additional)

                if reasoning_content:
                    if not reasoning_started:
                        yield _chunk("reasoning-start", completion_id)
                        reasoning_started = True
                    yield _chunk("reasoning-delta", completion_id, reasoning_content)
                    full_reasoning += reasoning_content
                    append_reasoning_part(reasoning_content)

                if content:
                    if not text_started:
                        yield _chunk("text-start", completion_id)
                        text_started = True
                    yield _chunk("text-delta", completion_id, content)
                    full_response += content
                    append_text_part(content)

            elif event_type == "on_chat_model_end":
                # Gemini often attaches full thinking blocks only on the final message, not in stream deltas.
                out = data.get("output")
                merged = _reasoning_from_ai_message(out)
                if merged and len(merged) > len(full_reasoning):
                    pending = merged[len(full_reasoning) :]
                    if pending:
                        if not reasoning_started:
                            yield _chunk("reasoning-start", completion_id)
                            reasoning_started = True
                        yield _chunk("reasoning-delta", completion_id, pending)
                        full_reasoning += pending
                        append_reasoning_part(pending)

                # Capture the last AIMessage so we can persist usage_metadata after the stream.
                if out is not None and getattr(out, "usage_metadata", None):
                    last_ai_message = out

        log.debug(
            "stream_loop_finished",
            chunks=_stream_chunk_i,
            text_len=len(full_response),
            reasoning_len=len(full_reasoning),
        )

    except asyncio.CancelledError:
        # Usuário clicou em "parar" no front (ou desconectou). Não re-raise:
        # deixar o `finally` persistir o que foi gerado até agora com o marker
        # "interrompido pelo usuário" para preservar contexto da conversa.
        was_cancelled = True
        log.info(
            "stream_cancelled_by_client",
            session_id=session_id,
            text_len=len(full_response),
            reasoning_len=len(full_reasoning),
            tool_calls=len(tool_parts_by_call_id),
        )
    except Exception as e:
        stream_failed = True
        log.exception("stream_agent_error", session_id=session_id, model=requested_model)
        yield _error_chunk(f"Streaming error: {e!s}")
    finally:
        # IMPORTANTE: spawn do save tem que rodar ANTES de qualquer `yield`
        # neste finally. Os yields de tag de fim podem disparar GeneratorExit
        # /CancelledError quando o consumer fechou o generator (cancel do
        # cliente). Como esses são BaseException, `contextlib.suppress(Exception)`
        # NÃO os captura — a exceção propaga e pula tudo abaixo, incluindo o save.
        if save_to_db and not stream_failed:
            try:
                if was_cancelled:
                    cancel_marker = "\n\n_Interrompido pelo usuário._"
                    if ordered_parts and ordered_parts[-1].get("type") == "text":
                        ordered_parts[-1]["text"] = (
                            ordered_parts[-1].get("text") or ""
                        ) + cancel_marker
                    else:
                        ordered_parts.append({"type": "text", "text": cancel_marker.lstrip()})
                    full_response = (full_response or "") + cancel_marker

                # História persistida usa texto puro — não infla JSONB com base64
                # de imagens. Os file parts vêm já saneados (URL servida por
                # /api/v1/uploads, sem base64) para que o frontend renderize
                # cards ao recarregar a thread.
                user_msg: dict[str, Any] = {
                    "role": "user",
                    "content": query_text_for_history,
                }
                if user_file_parts:
                    user_parts: list[dict[str, Any]] = []
                    if query_text_for_history:
                        user_parts.append({"type": "text", "text": query_text_for_history})
                    user_parts.extend(user_file_parts)
                    user_msg["parts"] = user_parts

                assistant_parts: list[dict[str, Any]] = list(ordered_parts)

                assistant_msg: dict = {"role": "assistant", "content": full_response}
                if full_reasoning:
                    assistant_msg["reasoning"] = full_reasoning
                if assistant_parts:
                    assistant_msg["parts"] = assistant_parts

                # Embed token/cost snapshot so the thread JSONB carries it for context
                # (the agent_message_usage table is the source of truth for analytics).
                usage_row = build_usage_from_ai_message(
                    last_ai_message,
                    thread_id=session_id,
                    message_id=completion_id,
                    agent_id=requested_model,
                    user_id=user_id,
                    client_id=active_client_id,
                )
                if usage_row is not None:
                    assistant_msg["usage"] = {
                        "provider": usage_row.provider,
                        "model_id": usage_row.model_id,
                        "input_tokens": usage_row.input_tokens,
                        "cached_input_tokens": usage_row.cached_input_tokens,
                        "output_tokens": usage_row.output_tokens,
                        "reasoning_tokens": usage_row.reasoning_tokens,
                        "total_tokens": usage_row.total_tokens,
                        "cost_usd": usage_row.cost_usd,
                    }

                # Detached task: read existing + append turn + save in one
                # scope. When the client cancels, ASGI re-emits cancel on every
                # await while closing the generator — `asyncio.shield` protects
                # the inner coroutine but the outer await still re-raises
                # CancelledError. `create_task` makes a sibling task that
                # survives the parent's cancellation and runs to completion.
                async def _detached_save(
                    sid: str,
                    uid: str,
                    aid: str,
                    new_messages: list[dict[str, Any]],
                    preview: str,
                ) -> None:
                    log.debug("detached_save_started", session_id=sid, new_msgs=len(new_messages))
                    try:
                        save_pool = await get_pool()
                        async with save_pool.acquire() as detached_conn:
                            existing = await _safe_get_chat_messages(detached_conn, sid)
                            full_history = list(existing or [])
                            full_history.extend(new_messages)
                            saved_thread = ChatHistoryThread(
                                thread_id=sid,
                                user_id=uid,
                                agent_id=aid,
                                messages=full_history,
                                preview=(preview[:PREVIEW_LENGTH] + "...")
                                if len(preview) > PREVIEW_LENGTH
                                else (preview or None),
                            )
                            await save_chat(detached_conn, saved_thread)
                        log.debug("detached_save_completed", session_id=sid)
                    except Exception:
                        log.exception("detached_save_failed", session_id=sid)

                new_turn_messages: list[dict[str, Any]] = [user_msg]
                if full_response or full_reasoning or assistant_parts:
                    new_turn_messages.append(assistant_msg)
                preview_seed = full_response or full_reasoning or query_text_for_history

                # Sempre fire-and-forget — mesmo no path normal — para evitar
                # qualquer await que possa ser interceptado por cancel tardio.
                _spawn_detached(
                    _detached_save(
                        session_id,
                        user_id,
                        requested_model,
                        new_turn_messages,
                        preview_seed,
                    )
                )
                log.debug("save_task_spawned", session_id=session_id)
            except BaseException:
                log.exception("persist_chat_history_failed", session_id=session_id)

        # End-tag yields — DEPOIS do save spawn. Em path normal funcionam; em
        # path cancelado o consumer fechou, o BaseException é suprimido aqui e
        # como o save já foi spawnado, o cancelamento desses yields é inofensivo.
        if reasoning_started:
            with contextlib.suppress(BaseException):
                yield _chunk("reasoning-end", completion_id)
        if stream_failed:
            if text_started:
                with contextlib.suppress(BaseException):
                    yield _chunk("text-end", completion_id)
        else:
            if not text_started:
                with contextlib.suppress(BaseException):
                    yield _chunk("text-start", completion_id)
            with contextlib.suppress(BaseException):
                yield _chunk("text-end", completion_id)

        finish_payload: dict = {"type": "finish"}
        if stream_failed:
            finish_payload["finishReason"] = "error"
        elif was_cancelled:
            finish_payload["finishReason"] = "stop"
        with contextlib.suppress(BaseException):
            yield f"data: {orjson.dumps(finish_payload).decode('utf-8')}\n\n"
