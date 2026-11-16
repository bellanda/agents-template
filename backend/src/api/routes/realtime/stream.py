"""`GET /realtime/stream`: the ONE per-user SSE channel (carries `entity.changed` and `batch`).

NO `Depends(get_conn)` on purpose: a pooled connection injected into a route that returns a
`StreamingResponse` is held until the stream ends (FastAPI closes `yield` dependencies after the
response is sent), i.e. one of the pool's `max_size` slots per open tab for hours (audit
2026-11-13 core-performance-01; guarded by `tests/core/test_streaming_routes_no_get_conn.py`).
The template has no organisations: identity is the verified user from `get_auth_context`. An app
with organisations resolves membership/permission with a SHORT `async with pool.acquire()` (or
`Depends(get_conn_scope)`) before returning, and hands the generator only the user id.
"""

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.services.auth import get_auth_context
from api.services.realtime.event_bus import event_bus
from api.services.realtime.sse import sse_response

router = APIRouter(prefix="/realtime", tags=["Realtime"])


@router.get("/stream", response_model=None)
async def realtime_stream(auth: dict[str, Any] = Depends(get_auth_context)) -> StreamingResponse:
    user_id = auth["user_id"]

    async def frames() -> AsyncIterator[str]:
        yield ": connected\n\n"
        async for frame in event_bus.subscribe(user_id):
            yield frame

    return sse_response(frames())
