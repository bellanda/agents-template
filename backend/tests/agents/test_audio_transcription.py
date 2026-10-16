"""Whisper upload goes through the REAL curl_cffi stack against a local HTTP server.

Regression (Promocar prod, 2026-10-16): `session.post(files=...)` raises `NotImplementedError` in
curl_cffi before any network I/O, so every customer audio came back "não consegui ouvir". Only a
test that lets curl build the request catches it — mocking `post` hides exactly that layer.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import orjson
import pytest

from api.core.agents import media

AUDIO_BYTES = b"OggS\x00fake-opus-payload"


class _FakeGroqHandler(BaseHTTPRequestHandler):
    received: ClassVar[dict[str, bytes]] = {}

    def do_POST(self) -> None:  # noqa: N802 — name fixed by http.server
        length = int(self.headers["Content-Length"])
        raw = f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode() + self.rfile.read(
            length
        )
        message = BytesParser(policy=HTTP).parsebytes(raw)
        _FakeGroqHandler.received = {
            part.get_param("name", header="content-disposition"): part.get_payload(decode=True)
            for part in message.iter_parts()
        }
        _FakeGroqHandler.received["filename"] = next(
            part.get_filename().encode() for part in message.iter_parts() if part.get_filename()
        )
        body = orjson.dumps({"text": "quero ver o civic", "duration": 3.0})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


@pytest.fixture
def fake_groq(monkeypatch) -> Iterator[None]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeGroqHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        media, "GROQ_TRANSCRIPTION_URL", f"http://127.0.0.1:{server.server_port}/transcriptions"
    )
    monkeypatch.setattr(media.integrations_config, "GROQ_API_KEY", "test-key")
    yield
    server.shutdown()


@pytest.mark.asyncio
async def test_customer_audio_is_uploaded_as_multipart_and_transcribed(fake_groq):
    result = await media.transcribe_audio(
        AUDIO_BYTES, filename="wa-audio-1.bin", mime_type="audio/ogg; codecs=opus"
    )

    assert result is not None
    assert result.text == "quero ver o civic"
    assert result.duration_seconds == 3.0
    received = _FakeGroqHandler.received
    assert received["file"] == AUDIO_BYTES
    assert received["filename"] == b"audio.ogg"  # Groq rejects ".bin"
    assert received["response_format"] == b"verbose_json"
    assert received["model"] == media.Models.Groq.WHISPER_LARGE_V3_TURBO.model_id.encode()
