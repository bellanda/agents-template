import contextlib
import os
from collections.abc import AsyncGenerator
from traceback import format_exc
from typing import Any

import orjson
from asyncpg.connection import Connection

from api.core.agents.models import compute_cost_usd, find_model_config
from api.models.agents.history import ChatHistoryThread
from api.models.agents.usage import AgentMessageUsage
from api.repositories.agents.chat_history import get_chat_messages, save_chat
from api.repositories.agents.usage import insert_agent_message_usage
from api.services.agents.executors import (
    extract_thinking_from_content,
    normalize_chunk_text,
    reasoning_from_additional_kwargs,
)

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
    query: str,
    user_id: str,
    session_id: str,
    completion_id: str,
    current_timestamp: int,
    requested_model: str,
    conn: Connection | None,
    realtor_id: int | None = None,
    active_client_id: str | None = None,
) -> AsyncGenerator[str]:
    """Stream agent events - Vercel AI SDK Data Stream Protocol (SSE)."""
    agent = agent_info["agent"]
    save_to_db: bool = agent_info.get("save_to_db", True)

    print(
        f"[stream_agent] model={requested_model!r} agent_type={type(agent).__name__} session_id={session_id!r} query_len={len(query)}"
    )
    yield f"data: {orjson.dumps({'type': 'start', 'messageId': completion_id}).decode('utf-8')}\n\n"

    reasoning_started = False
    text_started = False
    stream_failed = False
    full_response = ""
    full_reasoning = ""
    tool_parts_by_call_id: dict[str, dict[str, Any]] = {}
    tool_call_order: list[str] = []
    last_usage: dict[str, Any] | None = None
    last_provider: str | None = None
    last_model_id: str | None = None

    langgraph_config: dict = {
        "configurable": {
            "thread_id": session_id,
            "realtor_id": realtor_id,
            "active_client_id": active_client_id,
        },
        "metadata": {"user_id": user_id, "agent_id": requested_model},
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
                        print(
                            f"[stream_agent][stream] #{_stream_chunk_i} run={ev_run} "
                            f"name={ev_name!r} delta_chars={dc} total_chars≈{_stream_chars}",
                            flush=True,
                        )
                elif event_type in ("on_tool_start", "on_tool_end", "on_tool_error"):
                    print(
                        f"[stream_agent][tool] {event_type} run={ev_run} name={ev_name!r} input={_dev_preview(data.get('input'), 600)}",
                        flush=True,
                    )
                    if event_type in ("on_tool_end", "on_tool_error"):
                        print(
                            f"[stream_agent][tool] {event_type} output={_dev_preview(data.get('output'), 800)}",
                            flush=True,
                        )
                    if event_type == "on_tool_error" or err is not None:
                        print(
                            f"[stream_agent][tool] ERROR event={event_type!r} err={err!r}",
                            flush=True,
                        )
                elif event_type.startswith("on_chain") or event_type.startswith("on_chat_model"):
                    print(
                        f"[stream_agent][ev] {event_type} run={ev_run} name={ev_name!r} data_keys={list(data.keys())}",
                        flush=True,
                    )
                    if err is not None:
                        print(f"[stream_agent][ev] nested error: {err!r}", flush=True)
                else:
                    print(
                        f"[stream_agent][ev] {event_type} run={ev_run} name={ev_name!r} data_keys={list(data.keys())}",
                        flush=True,
                    )
                    if err is not None:
                        print(f"[stream_agent][ev] error field: {err!r}", flush=True)

            if event_type == "on_tool_start":
                tool_call_id = str(event.get("run_id") or "")
                tool_input = data.get("input")
                if tool_call_id and ev_name:
                    if tool_call_id not in tool_parts_by_call_id:
                        tool_call_order.append(tool_call_id)
                    tool_parts_by_call_id[tool_call_id] = {
                        "type": "dynamic-tool",
                        "toolName": ev_name,
                        "toolCallId": tool_call_id,
                        "state": "input-available",
                        "input": tool_input,
                    }
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
                    part = tool_parts_by_call_id.setdefault(
                        tool_call_id,
                        {
                            "type": "dynamic-tool",
                            "toolName": ev_name or "",
                            "toolCallId": tool_call_id,
                            "input": data.get("input"),
                        },
                    )
                    part["state"] = "output-available"
                    part["output"] = raw
                    if tool_call_id not in tool_call_order:
                        tool_call_order.append(tool_call_id)
                    yield _tool_output_chunk(tool_call_id, raw)
                continue

            if event_type == "on_tool_error":
                tool_call_id = str(event.get("run_id") or "")
                if tool_call_id:
                    error_message = str(err or "Tool failed")
                    part = tool_parts_by_call_id.setdefault(
                        tool_call_id,
                        {
                            "type": "dynamic-tool",
                            "toolName": ev_name or "",
                            "toolCallId": tool_call_id,
                            "input": data.get("input"),
                        },
                    )
                    part["state"] = "output-error"
                    part["errorText"] = error_message
                    if tool_call_id not in tool_call_order:
                        tool_call_order.append(tool_call_id)
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

                if content:
                    if not text_started:
                        yield _chunk("text-start", completion_id)
                        text_started = True
                    yield _chunk("text-delta", completion_id, content)
                    full_response += content

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

                # Capture token usage and the actual provider/model that just answered.
                if out is not None:
                    usage = getattr(out, "usage_metadata", None)
                    if usage:
                        last_usage = dict(usage)
                    rm = getattr(out, "response_metadata", None) or {}
                    provider = rm.get("model_provider")
                    model_id = rm.get("model_name") or rm.get("model")
                    if provider:
                        last_provider = str(provider)
                    if model_id:
                        last_model_id = str(model_id)

        if _agent_stream_debug():
            print(
                f"[stream_agent] stream loop finished OK chunks={_stream_chunk_i} "
                f"text_len={len(full_response)} reasoning_len={len(full_reasoning)}",
                flush=True,
            )

    except Exception as e:
        stream_failed = True
        print(
            f"[stream_agent] ERROR session_id={session_id!r} model={requested_model!r} {type(e).__name__}: {e}\n{format_exc()}"
        )
        yield _error_chunk(f"Streaming error: {e!s}")
    finally:
        if reasoning_started:
            yield _chunk("reasoning-end", completion_id)
        if stream_failed:
            if text_started:
                yield _chunk("text-end", completion_id)
        else:
            if not text_started:
                yield _chunk("text-start", completion_id)
            yield _chunk("text-end", completion_id)

        if save_to_db and conn and not stream_failed:
            try:
                history = await get_chat_messages(conn, session_id) or []
                history.append({"role": "user", "content": query})

                assistant_parts: list[dict[str, Any]] = []
                if full_reasoning:
                    assistant_parts.append({"type": "reasoning", "reasoning": full_reasoning})
                for call_id in tool_call_order:
                    part = tool_parts_by_call_id.get(call_id)
                    if part:
                        assistant_parts.append(part)
                if full_response:
                    assistant_parts.append({"type": "text", "text": full_response})

                assistant_msg: dict = {"role": "assistant", "content": full_response}
                if full_reasoning:
                    assistant_msg["reasoning"] = full_reasoning
                if assistant_parts:
                    assistant_msg["parts"] = assistant_parts

                # Embed token/cost snapshot so the thread JSONB carries it for context
                # (the agent_message_usage table is the source of truth for analytics).
                cost_usd = 0.0
                if last_usage:
                    cfg = (
                        find_model_config(last_provider, last_model_id)
                        if last_provider and last_model_id
                        else None
                    )
                    cost_usd = compute_cost_usd(last_usage, cfg) if cfg else 0.0
                    in_det = last_usage.get("input_token_details") or {}
                    out_det = last_usage.get("output_token_details") or {}
                    assistant_msg["usage"] = {
                        "provider": last_provider,
                        "model_id": last_model_id,
                        "input_tokens": int(last_usage.get("input_tokens") or 0),
                        "cached_input_tokens": int(in_det.get("cache_read") or 0),
                        "output_tokens": int(last_usage.get("output_tokens") or 0),
                        "reasoning_tokens": int(out_det.get("reasoning") or 0),
                        "total_tokens": int(last_usage.get("total_tokens") or 0),
                        "cost_usd": cost_usd,
                    }

                if full_response or full_reasoning or assistant_parts:
                    history.append(assistant_msg)

                preview_content = full_response or full_reasoning
                thread = ChatHistoryThread(
                    thread_id=session_id,
                    user_id=user_id,
                    agent_id=requested_model,
                    messages=history,
                    preview=(preview_content[:PREVIEW_LENGTH] + "...")
                    if len(preview_content) > PREVIEW_LENGTH
                    else (preview_content or None),
                )
                await save_chat(conn, thread)

                if last_usage and last_provider and last_model_id:
                    in_det = last_usage.get("input_token_details") or {}
                    out_det = last_usage.get("output_token_details") or {}
                    try:
                        await insert_agent_message_usage(
                            conn,
                            AgentMessageUsage(
                                thread_id=session_id,
                                message_id=completion_id,
                                user_id=user_id,
                                client_id=active_client_id,
                                agent_id=requested_model,
                                provider=last_provider,
                                model_id=last_model_id,
                                input_tokens=int(last_usage.get("input_tokens") or 0),
                                cached_input_tokens=int(in_det.get("cache_read") or 0),
                                output_tokens=int(last_usage.get("output_tokens") or 0),
                                reasoning_tokens=int(out_det.get("reasoning") or 0),
                                total_tokens=int(last_usage.get("total_tokens") or 0),
                                cost_usd=cost_usd,
                            ),
                        )
                    except Exception:
                        print(f"[stream_agent] failed to persist usage row\n{format_exc()}")
            except Exception:
                print(f"[stream_agent] failed to persist chat history\n{format_exc()}")

        finish_payload: dict = {"type": "finish"}
        if stream_failed:
            finish_payload["finishReason"] = "error"
        yield f"data: {orjson.dumps(finish_payload).decode('utf-8')}\n\n"
