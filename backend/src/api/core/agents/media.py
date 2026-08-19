"""Mídia em texto — o degrau que um agente text-only precisa para ouvir e enxergar.

O problema é sempre o mesmo em qualquer canal: o modelo de atendimento é de TEXTO, e chega
áudio, foto e PDF. Este módulo transforma bytes em frase ANTES do prompt, com uma cadeia de
degraus e um piso:

    áudio  → Whisper (Groq) → Gemini 3.7 Flash (aceita áudio) → None
    imagem → Gemini 3.7 Flash                                 → None
    PDF    → Gemini 3.7 Flash                                 → None

Nada aqui levanta exceção e nada aqui conhece o canal: a entrada é `bytes` + `mime_type`, a
saída é `str | None`. Quem chama decide o que fazer com o `None` — no WhatsApp vira um
placeholder ("o contato mandou um áudio e não foi possível ouvi-lo"), num chat vira o anexo
sem descrição. Acoplar isto a um canal é o que trava a reutilização.

Três decisões que valem a pena carregar para qualquer projeto:

1. **Whisper primeiro, multimodal depois.** Transcrever não precisa de raciocínio, e o
   Whisper na Groq é ordem de grandeza mais barato. O modelo caro é o degrau de queda, não a
   rota normal.
2. **A visão passa pelo LangChain.** É o que faz o `usage_recorder` lançar a linha em
   `agent_message_usage` de graça. Chamar o SDK cru — o atalho óbvio — deixa o custo da
   mídia invisível para qualquer teto de gasto.
3. **O custo do Whisper é lançado à mão.** Ele é um POST multipart, não passa pelo callback,
   e é cobrado por HORA de áudio. Sem esta linha o teto mensal mede só metade da fatura.
"""

import base64
import os
from dataclasses import dataclass
from typing import Any, Final

import anyio
from curl_cffi import AsyncSession
from langchain_core.messages import HumanMessage

from api.core.agents.callbacks import usage_recorder
from api.core.agents.custom_providers import init_model
from api.core.agents.models import Models, round_cost_up
from api.core.logging import get_logger
from api.models.agents.usage import AgentMessageUsage
from api.repositories.agents.usage import insert_agent_message_usage
from config import database as database_module

log = get_logger(__name__)

# Agente próprio na contabilidade: enriquecer mídia é uma despesa diferente de conversar, e
# separá-las é o que permite responder "quanto custou ouvir áudio este mês".
ENRICHMENT_AGENT_ID: Final = "media-enrichment"

VISION_MODEL: Final = Models.OpenRouter.GEMINI_3_7_FLASH
VISION_MAX_TOKENS: Final = 512

GROQ_TRANSCRIPTION_URL: Final = "https://api.groq.com/openai/v1/audio/transcriptions"
TRANSCRIPTION_LANGUAGE: Final = "pt"
TRANSCRIPTION_TIMEOUT_SECONDS: Final = 60.0

# Whisper cobra por HORA DE ÁUDIO, não por token — confira em groq.com/pricing ao mexer.
WHISPER_USD_PER_HOUR: Final = 0.04
SECONDS_PER_HOUR: Final = 3600.0

# Duas tentativas, não cinco: existe alguém esperando resposta do outro lado, e insistir num
# provedor fora do ar só atrasa a queda para o degrau seguinte, que provavelmente funciona.
MAX_ATTEMPTS: Final = 2
RETRY_BASE_DELAY_SECONDS: Final = 0.5

# 429 e 5xx passam; 401/400 não. Repetir credencial errada ou payload inválido é queimar
# tempo numa falha que não muda de resposta.
RETRYABLE_STATUS: Final[frozenset[int]] = frozenset({408, 409, 429, 500, 502, 503, 504})
HTTP_CLIENT_ERROR_FLOOR: Final = 400

# Teto do que vai inline para o modelo. Base64 infla 33%, então 5 MB de arquivo viram ~6,7 MB
# de request. O teto de armazenamento é outro (e maior): guardar um anexo grande é barato,
# mandá-lo para um modelo é que não é.
INLINE_MAX_BYTES: Final = 5 * 1024 * 1024

PDF_MIME: Final = "application/pdf"

IMAGE_PROMPT: Final = (
    "Descreva em português, de forma objetiva, o que aparece nesta imagem. "
    "Inclua qualquer texto legível: números, valores, datas, nomes. "
    "Responda apenas com a descrição, sem introduções."
)
DOCUMENT_PROMPT: Final = (
    "Resuma em português o conteúdo deste documento, preservando números, valores e datas. "
    "Responda apenas com o resumo, sem introduções."
)
AUDIO_PROMPT: Final = (
    "Transcreva este áudio em português. Responda apenas com a transcrição, sem introduções."
)


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    duration_seconds: float
    cost_usd: float


def _bare_mime(mime_type: str) -> str:
    return mime_type.split(";")[0].strip().lower()


def _family(mime_type: str) -> str:
    return _bare_mime(mime_type).split("/")[0]


def _cost_for(duration_seconds: float) -> float:
    return round_cost_up(duration_seconds / SECONDS_PER_HOUR * WHISPER_USD_PER_HOUR)


async def transcribe_audio(
    content: bytes, *, filename: str = "audio.ogg", mime_type: str = "audio/ogg"
) -> TranscriptionResult | None:
    """Áudio em texto pelo Whisper da Groq. `None` quando não deu — nunca levanta.

    O que NÃO se faz é engolir o motivo: cada falha sai no log com o `status_code`, porque
    "sem transcrição" por 401 (credencial) e por 429 (limite) se resolvem de formas opostas.

    `response_format=verbose_json` é o que devolve a `duration`, e sem ela não há como
    calcular o custo — a cobrança é por hora de áudio.

    `curl_cffi` e não o SDK `groq`: é o cliente HTTP do projeto, e o SDK traria httpx junto
    por uma chamada só.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        log.warning("transcription_unconfigured")
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
                text=text, duration_seconds=duration, cost_usd=_cost_for(duration)
            )
        except Exception:
            log.exception("transcription_failed", attempt=attempt)
            if attempt < MAX_ATTEMPTS:
                await anyio.sleep(RETRY_BASE_DELAY_SECONDS * 2 ** (attempt - 1))
                continue
            return None
    return None


def _content_parts(content: bytes, mime_type: str, filename: str) -> list[dict[str, Any]] | None:
    """As partes da mensagem multimodal, no formato que o OpenRouter espera por modalidade."""
    encoded = base64.b64encode(content).decode("ascii")
    bare = _bare_mime(mime_type)
    family = _family(mime_type)

    if family == "image":
        return [
            {"type": "text", "text": IMAGE_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:{bare};base64,{encoded}"}},
        ]
    if family == "audio":
        return [
            {"type": "text", "text": AUDIO_PROMPT},
            {
                "type": "input_audio",
                "input_audio": {"data": encoded, "format": bare.split("/")[-1]},
            },
        ]
    if bare == PDF_MIME:
        return [
            {"type": "text", "text": DOCUMENT_PROMPT},
            {
                "type": "file",
                "file": {
                    "filename": filename,
                    "file_data": f"data:{PDF_MIME};base64,{encoded}",
                },
            },
        ]
    return None


async def describe_media(
    content: bytes,
    *,
    mime_type: str,
    filename: str = "anexo",
    thread_id: str,
    agent_id: str = ENRICHMENT_AGENT_ID,
    user_id: str | None = None,
) -> str | None:
    """Imagem, PDF ou áudio em texto pelo Gemini 3.7 Flash. `None` quando não deu.

    `thread_id` e `agent_id` não são decoração: é por eles que o `usage_recorder` grava a
    linha de custo. Sem um dos dois o callback descarta a medição em silêncio, e o gasto com
    mídia deixa de existir para qualquer teto.
    """
    if len(content) > INLINE_MAX_BYTES:
        log.info("vision_skipped_too_large", byte_size=len(content), mime_type=mime_type)
        return None

    parts = _content_parts(content, mime_type, filename)
    if parts is None:
        log.info("vision_unsupported_mime", mime_type=mime_type)
        return None

    model = init_model(VISION_MODEL, streaming=False, max_tokens=VISION_MAX_TOKENS)
    config = {
        "callbacks": [usage_recorder],
        "metadata": {"thread_id": thread_id, "agent_id": agent_id, "user_id": user_id},
    }

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            reply = await model.ainvoke([HumanMessage(content=parts)], config=config)
        except Exception:
            log.exception("vision_failed", attempt=attempt, mime_type=mime_type)
            if attempt < MAX_ATTEMPTS:
                await anyio.sleep(RETRY_BASE_DELAY_SECONDS * 2 ** (attempt - 1))
                continue
            return None
        text = reply.text() if callable(getattr(reply, "text", None)) else str(reply.content)
        text = (text or "").strip()
        if text:
            return text
        log.info("vision_empty", mime_type=mime_type)
        return None
    return None


async def record_transcription_cost(
    result: TranscriptionResult,
    *,
    thread_id: str,
    message_id: str,
    agent_id: str = ENRICHMENT_AGENT_ID,
    user_id: str | None = None,
) -> None:
    """Lança o custo do Whisper à mão — ele não passa pelo `usage_recorder`.

    Tokens ficam em zero porque a cobrança é por hora de áudio; o que importa é o `cost_usd`,
    que é o número somado por qualquer teto de gasto. Falhar aqui não pode derrubar o
    enriquecimento: a transcrição já existe e vale mais que a linha de contabilidade.
    """
    pool = getattr(database_module, "asyncpg_pool", None)
    if pool is None:
        return
    usage = AgentMessageUsage(
        thread_id=thread_id,
        message_id=message_id,
        user_id=user_id,
        agent_id=agent_id,
        provider=Models.Groq.WHISPER_LARGE_V3_TURBO.provider,
        model_id=Models.Groq.WHISPER_LARGE_V3_TURBO.model_id,
        cost_usd=result.cost_usd,
    )
    try:
        async with pool.acquire() as conn:
            await insert_agent_message_usage(conn, usage)
    except Exception:
        log.exception("transcription_usage_insert_failed", thread_id=thread_id)


async def media_to_text(
    content: bytes,
    *,
    mime_type: str,
    filename: str = "anexo",
    thread_id: str,
    message_id: str,
    agent_id: str = ENRICHMENT_AGENT_ID,
    user_id: str | None = None,
) -> str | None:
    """A cadeia inteira: bytes de qualquer mídia em texto, ou `None`.

    Ponto de entrada único — quem chama não escolhe o degrau nem trata falha de provedor.
    """
    if _family(mime_type) == "audio":
        result = await transcribe_audio(content, filename=filename, mime_type=mime_type)
        if result is not None:
            await record_transcription_cost(
                result,
                thread_id=thread_id,
                message_id=message_id,
                agent_id=agent_id,
                user_id=user_id,
            )
            return result.text
        log.info("enrichment_falling_back_to_vision", message_id=message_id)

    return await describe_media(
        content,
        mime_type=mime_type,
        filename=filename,
        thread_id=thread_id,
        agent_id=agent_id,
        user_id=user_id,
    )
