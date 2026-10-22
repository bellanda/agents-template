"""Erros do navegador → log do backend (padrão da frota, 2026-10-22).

Cada evento vira UMA linha `client_error` no mesmo structlog/journald do backend, com
`source="frontend"`. O `client_request_id` é o `X-Request-ID` da resposta que falhou: buscar
por ele cai direto na linha do backend daquela chamada. Sem tabela de propósito — log de erro
é diagnóstico, e o destino dos logs da frota já é um só (`rules/logs.md`).
"""

import structlog
from fastapi import Request

from api.schemas.observability.client_logs import ClientLogBatch
from api.services.cache.valkey_client import get_valkey

log = structlog.get_logger(__name__)

CLIENT_LOG_THROTTLE_KEY = "client_logs:ip:{ip}"
CLIENT_LOG_WINDOW_SECONDS = 60
CLIENT_LOG_MAX_EVENTS_PER_WINDOW = 60
MAX_USER_AGENT_LENGTH = 300


async def is_client_log_allowed(ip: str, event_count: int) -> bool:
    """Janela fixa por IP, contada em EVENTOS. Fail-open: Valkey fora não perde o erro.

    Acima do teto o lote é descartado em silêncio (204): devolver erro faria o navegador tentar
    reenviar, e um loop de erro no front viraria um loop de requisições.
    """
    key = CLIENT_LOG_THROTTLE_KEY.format(ip=ip)
    try:
        pipe = get_valkey().pipeline(transaction=False)
        pipe.incrby(key, event_count)
        pipe.expire(key, CLIENT_LOG_WINDOW_SECONDS, nx=True)
        count, _ = await pipe.execute()
    except Exception:
        log.warning("client_log_throttle_failed", exc_info=True)
        return True
    return int(count) <= CLIENT_LOG_MAX_EVENTS_PER_WINDOW


def client_ip_from_request(request: Request) -> str:
    """X-Real-IP set by the reverse proxy (same rule as LoggingMiddleware), else the socket peer."""
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def write_client_logs(batch: ClientLogBatch, *, user_id: str | None, user_agent: str) -> None:
    for event in batch.events:
        log.warning(
            "client_error",
            source="frontend",
            level_reported=event.level,
            kind=event.kind,
            title=event.title,
            message=event.message,
            stack=event.stack,
            route=event.route,
            client_request_id=event.request_id,
            status=event.status,
            app_version=event.app_version,
            occurred_at=event.occurred_at.isoformat(),
            user_id=user_id,
            user_agent=user_agent[:MAX_USER_AGENT_LENGTH],
        )
