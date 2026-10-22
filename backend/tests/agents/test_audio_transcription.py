"""Whisper goes through the REAL curl_cffi stack against a local HTTP server (OpenRouter STT shape).

Regressions it guards:
- Promocar prod, 2026-10-16: `session.post(files=...)` raised `NotImplementedError` in curl_cffi
  before any network I/O, so every customer audio came back "não consegui ouvir". Only a test
  that lets curl build the request catches it — mocking `post` hides exactly that layer.
- 2026-10-16: the stored name ends in ".bin" and Whisper rejected it (400); the audio format
  must come from the MIME.
- 2026-10-22: Whisper moved from Groq-direct (multipart) to OpenRouter (JSON + base64); the cost
  OpenRouter reports is what gets billed.
"""

from __future__ import annotations

import base64
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import orjson
import pytest

from api.core.agents import media

AUDIO_BYTES = b"OggS\x00fake-opus-payload"


class _FakeOpenRouterHandler(BaseHTTPRequestHandler):
    received: ClassVar[dict] = {}
    replies: ClassVar[list[str]] = []
    calls: ClassVar[int] = 0
    path_seen: ClassVar[str] = ""
    auth_seen: ClassVar[str] = ""

    def do_POST(self) -> None:  # noqa: N802 — name fixed by http.server
        length = int(self.headers["Content-Length"])
        _FakeOpenRouterHandler.received = orjson.loads(self.rfile.read(length))
        _FakeOpenRouterHandler.path_seen = self.path
        _FakeOpenRouterHandler.auth_seen = self.headers["Authorization"]
        _FakeOpenRouterHandler.calls += 1
        text = _FakeOpenRouterHandler.replies.pop(0) if _FakeOpenRouterHandler.replies else ""
        body = orjson.dumps({"text": text, "usage": {"seconds": 3.0, "cost": 0.0000099}})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


@pytest.fixture
def fake_openrouter(monkeypatch) -> Iterator[None]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeOpenRouterHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        media.integrations_config,
        "OPENROUTER_API_BASE",
        f"http://127.0.0.1:{server.server_port}/api/v1",
    )
    monkeypatch.setattr(media.integrations_config, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(media, "RETRY_BASE_DELAY_SECONDS", 0)
    _FakeOpenRouterHandler.calls = 0
    yield
    server.shutdown()


@pytest.mark.asyncio
async def test_customer_audio_is_sent_as_base64_json_and_transcribed(fake_openrouter):
    _FakeOpenRouterHandler.replies = [" quero ver o civic "]
    result = await media.transcribe_audio(
        AUDIO_BYTES, filename="wa-audio-1.bin", mime_type="audio/ogg; codecs=opus"
    )

    assert result is not None
    assert result.text == "quero ver o civic"
    assert result.duration_seconds == 3.0
    assert result.cost_usd >= 0.0000099  # provider-reported cost wins (rounded up)
    received = _FakeOpenRouterHandler.received
    assert _FakeOpenRouterHandler.path_seen == "/api/v1/audio/transcriptions"
    assert _FakeOpenRouterHandler.auth_seen == "Bearer test-key"
    assert received["model"] == media.Models.OpenRouter.WHISPER_LARGE_V3_TURBO.model_id
    assert received["language"] == "pt"
    assert base64.b64decode(received["input_audio"]["data"]) == AUDIO_BYTES
    assert received["input_audio"]["format"] == "ogg"  # never "bin"


@pytest.mark.asyncio
async def test_an_empty_transcript_is_retried_once(fake_openrouter):
    """1 of 107 real voice notes came back empty, then full on retry (2026-10-22)."""
    _FakeOpenRouterHandler.replies = ["", "oi, tudo bem?"]
    result = await media.transcribe_audio(AUDIO_BYTES, mime_type="audio/ogg")
    assert result is not None and result.text == "oi, tudo bem?"
    assert _FakeOpenRouterHandler.calls == 2


@pytest.mark.parametrize(
    ("filename", "mime", "expected"),
    [
        ("wa-audio-1.bin", "audio/ogg; codecs=opus", "ogg"),
        ("arquivo", "audio/mpeg", "mp3"),
        ("voz.m4a", "audio/mp4", "m4a"),
        ("voz.webm", "application/octet-stream", "webm"),
        ("x", "audio/desconhecido", "ogg"),
    ],
)
def test_whisper_format_comes_from_the_mime_never_the_stored_name(filename, mime, expected):
    assert media.whisper_audio_format(filename, mime) == expected


def test_missing_provider_cost_falls_back_to_the_static_price():
    result = media.transcription_result_from_body({"text": "oi", "usage": {"seconds": 3600}})
    assert result is not None and result.cost_usd == media.WHISPER_USD_PER_HOUR
    assert media.transcription_result_from_body({"text": "  "}) is None


def test_whisper_is_never_instantiated_as_a_chat_model():
    """Before 2026-10-22 the "groq" provider blocked it; on OpenRouter only the flag does."""
    from api.core.agents.custom_providers import init_model

    with pytest.raises(ValueError, match="not instantiable"):
        init_model(media.Models.OpenRouter.WHISPER_LARGE_V3_TURBO)
