"""Media into text — the step a text-driven agent needs to hear and see.

The problem is the same on every channel: the conversation runs on TEXT, and audio, photos,
videos and PDFs arrive. This module turns bytes into sentences BEFORE the prompt, with a
chain of steps and a floor:

    audio  → Whisper (Groq) → multimodal model, IF it takes audio → None
    image  → multimodal model                                       → None
    video  → multimodal model, IF it takes video                    → None
    PDF    → multimodal model, IF it takes PDF (else see `ocr.py`)  → None

The "multimodal model" is the SAME one that chats (`VISION_MODEL`), not a separate vision
model: the stack is natively multimodal. Which steps exist comes from the `ModelConfig`
capability flags, not from an `if` written here — with GLM 5.3 Flash (text/image/video) the
PDF branch and the audio fallback are off, and a model with `file`/`audio` turns them on
without touching this file. Scanned PDFs are read page by page in `ocr.py`.

Nothing here raises and nothing here knows the channel: input is `bytes` + `mime_type`,
output is `str | None`. The caller decides what `None` means — on WhatsApp a placeholder
("the contact sent an audio that could not be heard"), in a chat an attachment with no
description. Coupling this to a channel is what kills reuse.

Decisions worth carrying to any project (the first three are exactly where apps that copied
this by hand went wrong):

1. **Whisper first, multimodal second.** Transcription needs no reasoning and Whisper on
   Groq is an order of magnitude cheaper. The expensive model is the fallback, not the route.
2. **Vision goes through LangChain** (`init_model` + `UsageContext.runnable_config()`), never
   the raw SDK. That is what makes `usage_recorder` write the cost row for free — the SDK
   shortcut makes media spend invisible to any cap.
3. **Whisper cost is recorded by hand** (`record_transcription_cost`): a multipart POST does
   not go through the callback, and it is billed per HOUR of audio.
4. **Differentiated retry, fail-soft.** 429/5xx retry (exponential backoff, 2 attempts —
   someone is waiting on the other side); 401/400 do not. Every failure is logged WITH its
   `status_code`, because "no transcript" by 401 and by 429 are fixed in opposite ways.
"""

import base64
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

import anyio
from curl_cffi import AsyncSession
from langchain_core.messages import HumanMessage

from api.core.agents.custom_providers import init_model
from api.core.agents.llm import UsageContext, cost_of
from api.core.agents.models import ModelConfig, Models, round_cost_up
from api.core.logging import get_logger
from api.models.agents.usage import AgentMessageUsage
from api.repositories.agents.usage import insert_agent_message_usage
from config import database as database_module
from config.integrations import integrations_config

log = get_logger(__name__)

# Own agent_id in the accounting: enriching media is a different expense from chatting, and
# separating them answers "how much did listening to audio cost this month".
ENRICHMENT_AGENT_ID: Final = "media-enrichment"

# The chat model, not a separate vision model — it is natively multimodal.
VISION_MODEL: Final = Models.OpenRouter.GLM_5_3_FLASH
VISION_MAX_TOKENS: Final = 512

GROQ_TRANSCRIPTION_URL: Final = "https://api.groq.com/openai/v1/audio/transcriptions"
TRANSCRIPTION_LANGUAGE: Final = "pt"
TRANSCRIPTION_TIMEOUT_SECONDS: Final = 60.0

# Whisper bills per HOUR OF AUDIO, not per token — check groq.com/pricing when changing it.
WHISPER_USD_PER_HOUR: Final = 0.04
SECONDS_PER_HOUR: Final = 3600.0

# Two attempts, not five: someone is waiting for a reply, and insisting on a provider that
# is down only delays the fall to the next step, which probably works.
MAX_ATTEMPTS: Final = 2
RETRY_BASE_DELAY_SECONDS: Final = 0.5

# 429 and 5xx pass; 401/400 do not. Repeating a wrong credential or invalid payload burns
# time on a failure whose answer never changes.
RETRYABLE_STATUS: Final[frozenset[int]] = frozenset({408, 409, 429, 500, 502, 503, 504})
HTTP_CLIENT_ERROR_FLOOR: Final = 400

# Ceiling of what goes INLINE to the model. Base64 inflates 33%, so 5 MB of file becomes
# ~6.7 MB of request. Storage has its own (larger) ceiling: keeping a big attachment is cheap,
# sending it to a model is not. Videos get more room because a few seconds already weigh MBs.
INLINE_MAX_BYTES: Final = 5 * 1024 * 1024
VIDEO_INLINE_MAX_BYTES: Final = 20 * 1024 * 1024

PDF_MIME: Final = "application/pdf"

# Prompts are pt-BR on purpose: the text they produce is shown to Brazilian end users and
# injected into pt-BR conversations.
IMAGE_PROMPT: Final = (
    "Descreva em português, de forma objetiva, o que aparece nesta imagem. "
    "Inclua qualquer texto legível: números, valores, datas, nomes. "
    "Responda apenas com a descrição, sem introduções."
)
VIDEO_PROMPT: Final = (
    "Descreva em português, de forma objetiva, o que acontece neste vídeo, incluindo texto "
    "legível e falas relevantes. Responda apenas com a descrição, sem introduções."
)
DOCUMENT_PROMPT: Final = (
    "Resuma em português o conteúdo deste documento, preservando números, valores e datas. "
    "Responda apenas com o resumo, sem introduções."
)
AUDIO_PROMPT: Final = (
    "Transcreva este áudio em português. Responda apenas com a transcrição, sem introduções."
)


def _with_extra(prompt: str, extra_instructions: str | None) -> str:
    """Canonical prompt + the app's domain hints appended — never replaced.

    WHY: apps add domain vocabulary (plates, bib numbers, deed terms) without forking the
    prompt, so every app keeps the byte-identical canonical prompt and improvements to it
    propagate from the template.
    """
    extra = (extra_instructions or "").strip()
    return f"{prompt} {extra}" if extra else prompt


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    duration_seconds: float
    cost_usd: float


@dataclass(frozen=True)
class VisionResult:
    """Text plus cost metadata — for callers that bill or report per operation (e.g. an
    inspection report built from N photos) without re-querying `agent_message_usage`."""

    text: str
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


def _bare_mime(mime_type: str) -> str:
    return mime_type.split(";")[0].strip().lower()


def _family(mime_type: str) -> str:
    return _bare_mime(mime_type).split("/")[0]


def _data_url(content: bytes, mime_type: str) -> str:
    return f"data:{_bare_mime(mime_type)};base64,{base64.b64encode(content).decode('ascii')}"


def transcription_cost_usd(duration_seconds: float) -> float:
    """USD to transcribe `duration_seconds` of audio (Groq bills per hour)."""
    return round_cost_up(max(duration_seconds, 0.0) / SECONDS_PER_HOUR * WHISPER_USD_PER_HOUR)


async def transcribe_audio(
    content: bytes, *, filename: str = "audio.ogg", mime_type: str = "audio/ogg"
) -> TranscriptionResult | None:
    """Audio into text with Groq's Whisper. `None` when it fails — never raises.

    `response_format=verbose_json` is what returns `duration`; without it there is no way to
    compute the cost (billing is per hour of audio). `curl_cffi`, not the `groq` SDK: it is
    the project's HTTP client, and the SDK would drag httpx in for a single call.
    """
    api_key = integrations_config.GROQ_API_KEY
    if not api_key:
        log.warning("transcription_unconfigured")
        return None
    if not content:
        return None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with AsyncSession() as session:
                response = await session.post(
                    GROQ_TRANSCRIPTION_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (filename, content, mime_type)},
                    data={
                        "model": Models.Groq.WHISPER_LARGE_V3_TURBO.model_id,
                        "language": TRANSCRIPTION_LANGUAGE,
                        "response_format": "verbose_json",
                    },
                    timeout=TRANSCRIPTION_TIMEOUT_SECONDS,
                )
            if response.status_code >= HTTP_CLIENT_ERROR_FLOOR:
                log.warning(
                    "transcription_http_error", status_code=response.status_code, attempt=attempt
                )
                if response.status_code in RETRYABLE_STATUS and attempt < MAX_ATTEMPTS:
                    await anyio.sleep(RETRY_BASE_DELAY_SECONDS * 2 ** (attempt - 1))
                    continue
                return None

            body = response.json()
            text = (body.get("text") or "").strip()
            if not text:
                log.info("transcription_empty")
                return None
            duration = float(body.get("duration") or 0.0)
            return TranscriptionResult(
                text=text, duration_seconds=duration, cost_usd=transcription_cost_usd(duration)
            )
        except Exception:
            log.exception("transcription_failed", attempt=attempt)
            if attempt < MAX_ATTEMPTS:
                await anyio.sleep(RETRY_BASE_DELAY_SECONDS * 2 ** (attempt - 1))
                continue
            return None
    return None


def _content_parts(
    content: bytes,
    mime_type: str,
    filename: str,
    cfg: ModelConfig = VISION_MODEL,
    extra_instructions: str | None = None,
) -> list[dict[str, Any]] | None:
    """Multimodal message parts, in the shape OpenRouter expects per modality.

    Each branch is gated by the model's DECLARED capability. Sending a PDF to a model that
    does not take `file` does not degrade — the upstream rejects the whole request and the
    user sees the attachment vanish unexplained. Returning `None` here falls back to the
    caller's placeholder, which is a readable failure. `extra_instructions` is appended to the
    image/video/document prompt (audio is transcription: no domain hints).
    """
    bare = _bare_mime(mime_type)
    family = _family(mime_type)
    limit = VIDEO_INLINE_MAX_BYTES if family == "video" else INLINE_MAX_BYTES
    if len(content) > limit:
        log.info("media_inline_too_large", byte_size=len(content), mime_type=bare)
        return None

    if family == "image" and cfg.supports_image_input:
        return [
            {"type": "text", "text": _with_extra(IMAGE_PROMPT, extra_instructions)},
            {"type": "image_url", "image_url": {"url": _data_url(content, bare)}},
        ]
    if family == "video" and cfg.supports_video_input:
        # OpenRouter's video part: `video_url` with a URL or base64 data URL.
        return [
            {"type": "text", "text": _with_extra(VIDEO_PROMPT, extra_instructions)},
            {"type": "video_url", "video_url": {"url": _data_url(content, bare)}},
        ]
    if family == "audio" and cfg.supports_audio_input:
        return [
            {"type": "text", "text": AUDIO_PROMPT},
            {
                "type": "input_audio",
                "input_audio": {
                    "data": base64.b64encode(content).decode("ascii"),
                    "format": bare.split("/")[-1],
                },
            },
        ]
    if bare == PDF_MIME and cfg.supports_pdf_input:
        return [
            {"type": "text", "text": _with_extra(DOCUMENT_PROMPT, extra_instructions)},
            {"type": "file", "file": {"filename": filename, "file_data": _data_url(content, bare)}},
        ]
    return None


async def _invoke_vision(
    parts: list[dict[str, Any]], *, usage: UsageContext | None, max_tokens: int, label: str
) -> VisionResult | None:
    """One multimodal call with the media retry policy. `None` on failure/empty."""
    model = init_model(VISION_MODEL, streaming=False, max_tokens=max_tokens)
    config = usage.runnable_config() if usage else {}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            reply = await model.ainvoke([HumanMessage(content=parts)], config=config)
        except Exception:
            log.exception("vision_failed", attempt=attempt, label=label)
            if attempt < MAX_ATTEMPTS:
                await anyio.sleep(RETRY_BASE_DELAY_SECONDS * 2 ** (attempt - 1))
                continue
            return None
        text = (reply.text or "").strip()
        if not text:
            log.info("vision_empty", label=label)
            return None
        tokens = reply.usage_metadata or {}
        cost, _ = cost_of(reply, VISION_MODEL)
        return VisionResult(
            text=text,
            model_id=VISION_MODEL.model_id,
            input_tokens=int(tokens.get("input_tokens") or 0),
            output_tokens=int(tokens.get("output_tokens") or 0),
            cost_usd=cost,
        )
    return None


async def describe_media(
    content: bytes,
    *,
    mime_type: str,
    filename: str = "anexo",
    usage: UsageContext,
    extra_instructions: str | None = None,
) -> str | None:
    """Image, video, PDF or audio into text with the multimodal model. `None` when it fails.

    `extra_instructions`: domain hints appended to the canonical prompt (never replacing it).
    WHY: apps add their vocabulary (e.g. "focus on license plates") without forking the prompt.

    `usage` is not decoration: its thread_id/agent_id are how the `usage_recorder` writes the
    cost row. Without them the callback drops the measurement silently.
    """
    parts = _content_parts(content, mime_type, filename, extra_instructions=extra_instructions)
    if parts is None:
        log.info("vision_unsupported_mime", mime_type=mime_type)
        return None
    result = await _invoke_vision(
        parts, usage=usage, max_tokens=VISION_MAX_TOKENS, label=_bare_mime(mime_type)
    )
    return result.text if result else None


async def describe_images(
    images: Sequence[tuple[bytes, str]],
    *,
    prompt: str = IMAGE_PROMPT,
    context: str | None = None,
    max_tokens: int = VISION_MAX_TOKENS,
    usage: UsageContext | None,
    extra_instructions: str | None = None,
) -> VisionResult | None:
    """N images in ONE call → `VisionResult` (text + cost), or `None`.

    `images` are `(bytes, mime_type)` pairs. One call for all photos (kailos/balizap vehicle
    assessment): the model must compare the angles with each other, and N isolated calls lose
    that while paying the prompt N times. `context` is extra text (e.g. the listing data) the
    model should read alongside the images. `extra_instructions` is appended to `prompt` (never
    replacing it): apps add domain vocabulary without forking the canonical prompt.
    """
    blocks: list[dict[str, Any]] = [
        {"type": "text", "text": _with_extra(prompt, extra_instructions)}
    ]
    if context:
        blocks.append({"type": "text", "text": context})
    image_blocks = [
        {"type": "image_url", "image_url": {"url": _data_url(content, mime)}}
        for content, mime in images
        if content and len(content) <= INLINE_MAX_BYTES
    ]
    if not image_blocks:
        return None
    return await _invoke_vision(
        [*blocks, *image_blocks], usage=usage, max_tokens=max_tokens, label="images"
    )


async def record_transcription_cost(
    result: TranscriptionResult, *, usage: UsageContext, message_id: str
) -> None:
    """Record Whisper's cost by hand — it does not go through `usage_recorder`.

    Tokens stay zero because billing is per hour of audio; `cost_usd` is what any spend cap
    sums. Failing here must not break enrichment: the transcript exists and is worth more
    than the accounting row.
    """
    pool = getattr(database_module, "asyncpg_pool", None)
    if pool is None:
        return
    row = AgentMessageUsage(
        thread_id=usage.thread_id,
        message_id=message_id,
        user_id=usage.user_id,
        client_id=usage.client_id,
        tenant_id=usage.tenant_id,
        agent_id=usage.agent_id,
        provider=Models.Groq.WHISPER_LARGE_V3_TURBO.provider,
        model_id=Models.Groq.WHISPER_LARGE_V3_TURBO.model_id,
        cost_usd=result.cost_usd,
    )
    try:
        async with pool.acquire() as conn:
            await insert_agent_message_usage(conn, row)
    except Exception:
        log.exception("transcription_usage_insert_failed", thread_id=usage.thread_id)


async def media_to_text(
    content: bytes,
    *,
    mime_type: str,
    filename: str = "anexo",
    usage: UsageContext,
    message_id: str,
    extra_instructions: str | None = None,
) -> str | None:
    """The whole chain: bytes of any media into text, or `None`.

    Single entry point — the caller neither picks the step nor handles provider failures.
    `extra_instructions`: domain hints appended to the canonical vision prompt (never replacing
    it), so apps add vocabulary without forking the prompt. Not used for audio transcription.

    Example (WhatsApp inbound, text-only attendant):
        text = await media_to_text(
            content, mime_type="audio/ogg", filename="audio.ogg",
            usage=UsageContext(thread_id=thread_id, agent_id=ENRICHMENT_AGENT_ID,
                               tenant_id=org_id),
            message_id=str(message_id),
        )
    """
    if _family(mime_type) == "audio":
        result = await transcribe_audio(content, filename=filename, mime_type=mime_type)
        if result is not None:
            await record_transcription_cost(result, usage=usage, message_id=message_id)
            return result.text
        # The fallback step only exists if the model really takes audio. With a text/image
        # model (GLM 5.3 Flash) `describe_media` would return None anyway — but the log would
        # claim a fallback happened, and it did not.
        if not VISION_MODEL.supports_audio_input:
            return None
        log.info("enrichment_falling_back_to_vision", message_id=message_id)

    return await describe_media(
        content,
        mime_type=mime_type,
        filename=filename,
        usage=usage,
        extra_instructions=extra_instructions,
    )
