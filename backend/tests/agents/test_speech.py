"""Text-to-speech goes through the REAL curl_cffi stack against a local HTTP server (OpenRouter shape).

Regressions it guards:
- kailos prod, 2026-10-23: the real cost was looked up with `GET /generation` right after the call,
  OpenRouter indexes it ~11 s later, and 111 of 111 TV alerts were billed a flat US$ 0.0003 guess.
  The bill is now the per-character price, which must reproduce real generations.
- The voice clone travels as `input_references` = [WAV data URL, transcript]; no `voice` key.
"""

from __future__ import annotations

import base64
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import orjson
import pytest

from api.core.agents import speech

MP3_BYTES = b"ID3\x04fake-mp3-frames"
REFERENCE_WAV = b"RIFF\x24\x00\x00\x00WAVEfake"


class _FakeOpenRouterHandler(BaseHTTPRequestHandler):
    received: ClassVar[list[dict]] = []
    path_seen: ClassVar[str] = ""
    auth_seen: ClassVar[str] = ""
    status: ClassVar[int] = 200
    audio: ClassVar[bytes] = MP3_BYTES

    def do_POST(self) -> None:  # noqa: N802 — name fixed by http.server
        length = int(self.headers["Content-Length"])
        _FakeOpenRouterHandler.received.append(orjson.loads(self.rfile.read(length)))
        _FakeOpenRouterHandler.path_seen = self.path
        _FakeOpenRouterHandler.auth_seen = self.headers["Authorization"]
        self.send_response(_FakeOpenRouterHandler.status)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("X-Generation-Id", f"gen-tts-{len(_FakeOpenRouterHandler.received)}")
        self.send_header("Content-Length", str(len(_FakeOpenRouterHandler.audio)))
        self.end_headers()
        self.wfile.write(_FakeOpenRouterHandler.audio)

    def log_message(self, *_args) -> None:
        return


@pytest.fixture
def fake_openrouter(monkeypatch) -> Iterator[type[_FakeOpenRouterHandler]]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeOpenRouterHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        speech.integrations_config,
        "OPENROUTER_API_BASE",
        f"http://127.0.0.1:{server.server_port}/api/v1",
    )
    monkeypatch.setattr(speech.integrations_config, "OPENROUTER_API_KEY", "test-key")
    _FakeOpenRouterHandler.received = []
    _FakeOpenRouterHandler.status = 200
    _FakeOpenRouterHandler.audio = MP3_BYTES
    yield _FakeOpenRouterHandler
    server.shutdown()


@pytest.mark.asyncio
async def test_cloned_voice_is_requested_as_mp3_and_returns_audio_id_and_price(fake_openrouter):
    reference = speech.SpeechReference(wav=REFERENCE_WAV, transcript="Aqui é o Maurício, da loja.")

    result = await speech.synthesize_speech("Venda fechada!", "Fale animado.", reference)

    assert result.audio == MP3_BYTES and result.mime_type == "audio/mpeg"
    assert result.generation_id == "gen-tts-1"
    assert result.cost_usd == speech.speech_cost_usd("Venda fechada!", "Fale animado.")
    assert fake_openrouter.path_seen == "/api/v1/audio/speech"
    assert fake_openrouter.auth_seen == "Bearer test-key"
    (body,) = fake_openrouter.received
    assert body["model"] == speech.SPEECH_MODEL.model_id == "fish-audio/drama-3"
    assert (body["input"], body["instructions"], body["response_format"]) == (
        "Venda fechada!",
        "Fale animado.",
        "mp3",
    )
    assert "voice" not in body
    audio_ref, transcript_ref = body["input_references"]
    encoded = audio_ref["input_audio"]["data"].removeprefix("data:audio/wav;base64,")
    assert base64.b64decode(encoded) == REFERENCE_WAV
    assert transcript_ref == {"type": "text", "text": "Aqui é o Maurício, da loja."}

    await speech.synthesize_speech("Oi.", "", None)
    assert "input_references" not in fake_openrouter.received[1]


@pytest.mark.parametrize(("status", "audio"), [(503, b"busy"), (200, b"")])
@pytest.mark.asyncio
async def test_provider_error_or_empty_audio_raises_for_the_caller_fallback(
    fake_openrouter, status, audio
):
    fake_openrouter.status, fake_openrouter.audio = status, audio
    with pytest.raises(speech.SpeechSynthesisError):
        await speech.synthesize_speech("Novo lead.", "Fale firme.")


# (characters of text, characters of instructions, real `total_cost` of `GET /generation`) — Fish
# generations from kailos prod on 2026-10-23, the last one with no voice clone. A cloned voice's
# ~700-character transcript is NOT billed: these rows had one and still match text + tone only.
REAL_GENERATIONS = [(52, 43, 0.000202), (65, 79, 0.000302), (55, 43, 0.000208), (15, 28, 0.000094)]
MAX_PRICE_DEVIATION = 0.05


@pytest.mark.parametrize(("text_chars", "instructions_chars", "real_cost"), REAL_GENERATIONS)
def test_per_character_price_reproduces_real_generations(text_chars, instructions_chars, real_cost):
    estimate = speech.speech_cost_usd("a" * text_chars, "b" * instructions_chars)
    assert abs(estimate - real_cost) / real_cost <= MAX_PRICE_DEVIATION
