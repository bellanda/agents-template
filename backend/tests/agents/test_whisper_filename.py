"""Groq Whisper valida o upload pela EXTENSÃO do nome (regressão kailos/nexarena, 2026-10-16)."""

import pytest

from api.core.agents.media import whisper_upload_filename


@pytest.mark.parametrize(
    ("filename", "mime", "expected"),
    [
        ("wa-audio-1.bin", "audio/ogg; codecs=opus", "audio.ogg"),
        ("arquivo", "audio/mpeg", "audio.mp3"),
        ("voz.m4a", "audio/mp4", "voz.m4a"),
        ("x", "audio/desconhecido", "audio.ogg"),
    ],
)
def test_whisper_always_gets_an_extension_groq_accepts(filename, mime, expected):
    assert whisper_upload_filename(filename, mime) == expected
