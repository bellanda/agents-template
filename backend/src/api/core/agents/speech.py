"""Text into speech — the ONE place that turns a sentence into audio (the mirror of `media.py`).

Optional module: only apps that SPEAK carry it (`sync_agents_to_another_fastapi_project.py
--add-module speech`). First caller: kailos TV mode alerts (`services/tv/voice_service.py`).

What lives here and what does not:
- here: the provider call (`POST {OPENROUTER_API_BASE}/audio/speech`), the optional voice clone
  (`SpeechReference`), the cost of each generation and its row in `agent_message_usage`;
- in the caller: WHAT to say and in which tone, caching (generate each phrase ONCE), storage and
  the spend-cap POLICY (kailos: `services/agents/ai_budget.py`) — this module measures, the app
  decides. A cache hit costs nothing: bill only what `synthesize_speech` returned.

Swapping the voice model = editing `SPEECH_MODEL` (a `ModelConfig` in `models.py`, price per
character in `input_price_per_1m`). If the app clones voices, first check
`supports_voice_cloning` in `GET /api/v1/models/<id>/endpoints`: ElevenLabs on OpenRouter does
not clone and Gemini TTS returns only PCM (bake-off 2026-10-23, skill `ai-agents` → media-ocr §TTS).

Cost — unlike chat and Whisper, the PRICE TABLE is billed, not the reported cost:
- the speech endpoint answers only the audio + `X-Generation-Id`; the real cost lives at
  `GET /generation?id=`, which OpenRouter indexes ~11 s AFTER the audio is back (measured
  2026-10-23). Looking it up right after the call 404'd on 111 of 111 kailos prod alerts, and every
  row fell back to a flat guess. Waiting would hold whoever waits for the audio (the store's alert
  lock, the 15 s warm-up lead of a TV alert);
- Fish bills per CHARACTER of `input` + `instructions` (injected as a bracketed direction, a few
  extra characters), and the voice-reference transcript is NOT billed. That rule reproduced 4 real
  generations within 1 to 4% (2026-10-23), so the row is written right away with it. If the provider
  changes the price, update `input_price_per_1m` from the endpoints listing above.
"""

import base64
from dataclasses import dataclass
from typing import Any, Final

from curl_cffi import AsyncSession

from api.core.agents.llm import UsageContext
from api.core.agents.models import Models, round_cost_up
from api.core.logging import get_logger
from api.models.agents.usage import AgentMessageUsage
from api.repositories.agents.usage import insert_agent_message_usage
from config import database as database_module
from config.integrations import integrations_config

log = get_logger(__name__)

SPEECH_MODEL: Final = Models.OpenRouter.FISH_AUDIO_DRAMA_3
SPEECH_PATH: Final = "/audio/speech"
SPEECH_RESPONSE_FORMAT: Final = "mp3"
SPEECH_MIME_TYPE: Final = "audio/mpeg"
REFERENCE_MIME_TYPE: Final = "audio/wav"
# Callers with someone waiting pass their own, tighter ceiling (kailos TV: 8 s).
DEFAULT_SPEECH_TIMEOUT_SECONDS: Final = 15.0
# Characters Fish adds around `instructions` when injecting them as a direction (measured 4 to 7).
DIRECTION_OVERHEAD_CHARACTERS: Final = 6
CHARACTERS_PER_PRICE_UNIT: Final = 1_000_000
HTTP_ERROR_FLOOR: Final = 400
# `message_id` of a row whose generation came back without `X-Generation-Id` (not seen so far).
UNIDENTIFIED_GENERATION_ID: Final = "speech-unidentified"


class SpeechSynthesisError(RuntimeError):
    """The provider answered an error or no audio; the caller picks its fallback."""


@dataclass(frozen=True)
class SpeechReference:
    """Voice to clone: a treated WAV (≤ 60 s) and what is said in it (Whisper transcript)."""

    wav: bytes
    transcript: str


@dataclass(frozen=True)
class SpeechResult:
    audio: bytes
    generation_id: str | None
    cost_usd: float
    mime_type: str = SPEECH_MIME_TYPE


def speech_cost_usd(text: str, instructions: str) -> float:
    """What one generation costs: per character of `text` + the bracketed `instructions`."""
    direction = len(instructions) + DIRECTION_OVERHEAD_CHARACTERS if instructions else 0
    characters = len(text) + direction
    return round_cost_up(characters * SPEECH_MODEL.input_price_per_1m / CHARACTERS_PER_PRICE_UNIT)


def build_speech_body(
    text: str, instructions: str, reference: SpeechReference | None
) -> dict[str, Any]:
    """`/audio/speech` body. No `voice` key: drama-3 ignores it; the tone goes in `instructions`."""
    body: dict[str, Any] = {
        "model": SPEECH_MODEL.model_id,
        "input": text,
        "response_format": SPEECH_RESPONSE_FORMAT,
        "instructions": instructions,
    }
    if reference is not None:
        encoded = base64.b64encode(reference.wav).decode("ascii")
        body["input_references"] = [
            {
                "type": "input_audio",
                "input_audio": {"data": f"data:{REFERENCE_MIME_TYPE};base64,{encoded}"},
            },
            {"type": "text", "text": reference.transcript},
        ]
    return body


async def synthesize_speech(
    text: str,
    instructions: str,
    reference: SpeechReference | None = None,
    *,
    timeout_seconds: float = DEFAULT_SPEECH_TIMEOUT_SECONDS,
) -> SpeechResult:
    """`text` spoken in the `instructions` tone, cloning `reference` when given.

    Raises `SpeechSynthesisError` on HTTP error or empty audio, with no retry: whoever waits (a TV
    alert) has a hard ceiling and a fallback, and a second attempt only delays it. Does NOT bill —
    pass the result to `record_speech_cost` (a paid generation is billed even if storing it fails).
    """
    url = integrations_config.OPENROUTER_API_BASE.rstrip("/") + SPEECH_PATH
    async with AsyncSession() as session:
        response = await session.post(
            url,
            headers={"Authorization": f"Bearer {integrations_config.OPENROUTER_API_KEY}"},
            json=build_speech_body(text, instructions, reference),
            timeout=timeout_seconds,
        )
    model_id = SPEECH_MODEL.model_id
    if response.status_code >= HTTP_ERROR_FLOOR:
        raise SpeechSynthesisError(
            f"speech_http_error: status {response.status_code} for model {model_id}"
        )
    if not response.content:
        raise SpeechSynthesisError(
            f"speech_empty_audio: model {model_id} returned no bytes for {text!r}"
        )
    return SpeechResult(
        audio=response.content,
        generation_id=response.headers.get("X-Generation-Id"),
        cost_usd=speech_cost_usd(text, instructions),
    )


async def record_speech_cost(result: SpeechResult, *, usage: UsageContext) -> None:
    """One `agent_message_usage` row per paid generation — what any spend cap sums.

    Tokens stay zero: the bill is per character. Failing to write must not surface — the audio
    exists and is worth more than the accounting row.
    """
    pool = getattr(database_module, "asyncpg_pool", None)
    if pool is None:
        return
    row = AgentMessageUsage(
        thread_id=usage.thread_id,
        message_id=result.generation_id or UNIDENTIFIED_GENERATION_ID,
        user_id=usage.user_id,
        client_id=usage.client_id,
        tenant_id=usage.tenant_id,
        agent_id=usage.agent_id,
        provider=SPEECH_MODEL.provider,
        model_id=SPEECH_MODEL.model_id,
        cost_usd=result.cost_usd,
    )
    try:
        async with pool.acquire() as conn:
            await insert_agent_message_usage(conn, row)
    except Exception:
        log.exception("speech_usage_insert_failed", thread_id=usage.thread_id)
