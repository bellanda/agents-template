"""NATS connection singleton — inicializado no lifespan do FastAPI.

- `connect_nats()` abre a conexão e declara os streams JetStream (idempotente).
- `close_nats()` faz drain+close graceful.
- `get_nc()` / `get_js()` retornam a conexão viva; levantam RuntimeError se chamados
  antes do startup terminar, por design (fail-fast).
"""

from __future__ import annotations

from typing import Any

import nats
import structlog
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from nats.js.api import RetentionPolicy, StorageType
from nats.js.errors import NotFoundError

from api.services.messaging.streams import STREAM_DEFINITIONS, StreamDefinition
from config.messaging import messaging_config

log = structlog.get_logger(__name__)

_nc: NATSClient | None = None
_js: JetStreamContext | None = None


async def _on_error(exc: Exception) -> None:
    log.warning("nats_error", error=str(exc))


async def _on_disconnected() -> None:
    log.warning("nats_disconnected")


async def _on_reconnected() -> None:
    log.info("nats_reconnected", url=_nc.connected_url.netloc if _nc else None)
    # Re-declara os streams (idempotente) ao reconectar: cobre o caso de o servidor NATS
    # ter perdido estado JetStream (volume recriado) durante a desconexão. Consumers
    # se recuperam via o handler de ServiceUnavailableError no fetch loop.
    if _js is not None:
        for definition in STREAM_DEFINITIONS:
            try:
                await _declare_stream(_js, definition)
            except Exception as exc:
                log.warning("nats_stream_redeclare_failed", stream=definition.name, error=str(exc))


async def _on_closed() -> None:
    log.info("nats_connection_closed")


async def _declare_stream(js: JetStreamContext, definition: StreamDefinition) -> None:
    # `max_age` é em segundos conforme `nats.js.api.StreamConfig` (convertido
    # internamente para nanossegundos pelo client antes de sair na wire).
    common_kwargs: dict[str, Any] = {
        "name": definition.name,
        "subjects": list(definition.subjects),
        "retention": RetentionPolicy.WORK_QUEUE,
        "storage": StorageType.FILE,
        "max_age": float(definition.max_age_seconds),
    }
    try:
        await js.stream_info(definition.name)
        log.info("nats_stream_exists", stream=definition.name)
    except NotFoundError:
        await js.add_stream(**common_kwargs)
        log.info(
            "nats_stream_created",
            stream=definition.name,
            subjects=list(definition.subjects),
            max_age_seconds=definition.max_age_seconds,
        )


async def connect_nats() -> None:
    global _nc, _js
    if _nc is not None and _nc.is_connected:
        return

    _nc = await nats.connect(
        servers=[messaging_config.NATS_URL],
        allow_reconnect=True,
        max_reconnect_attempts=messaging_config.NATS_MAX_RECONNECT_ATTEMPTS,
        reconnect_time_wait=messaging_config.NATS_RECONNECT_TIME_WAIT,
        connect_timeout=messaging_config.NATS_CONNECT_TIMEOUT,
        name="agents-template-backend",
        error_cb=_on_error,
        disconnected_cb=_on_disconnected,
        reconnected_cb=_on_reconnected,
        closed_cb=_on_closed,
    )
    _js = _nc.jetstream()
    log.info("nats_connected", url=messaging_config.NATS_URL)

    for definition in STREAM_DEFINITIONS:
        await _declare_stream(_js, definition)


async def close_nats() -> None:
    global _nc, _js
    if _nc is None:
        return
    try:
        await _nc.drain()
    except Exception as exc:
        log.warning("nats_drain_failed", error=str(exc))
    _nc = None
    _js = None


def get_nc() -> NATSClient:
    if _nc is None:
        raise RuntimeError("NATS client not initialized — did lifespan startup run?")
    return _nc


def get_js() -> JetStreamContext:
    if _js is None:
        raise RuntimeError("JetStream not initialized — did lifespan startup run?")
    return _js
