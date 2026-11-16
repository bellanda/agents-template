"""SSE response factory: the headers every stream route must send (one place, no drift)."""

from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse


def sse_response(frames: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        frames,
        media_type="text/event-stream",
        headers={
            # `no-transform`: without it Cloudflare compresses/buffers the text/event-stream and
            # nothing reaches the browser until the connection drops (~125 s) — Kailos prod 2026-10-09.
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
