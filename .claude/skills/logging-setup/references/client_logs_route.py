# --- schemas/observability/client_logs.py ---
"""Lote de erros que o navegador manda para `POST /client-logs` (padrão da frota, 2026-10-22).

Só campos de diagnóstico: nunca corpo de request, token, telefone ou e-mail — o schema não tem
onde pôr. Os limites seguram o tamanho do lote, porque a rota é pública (o erro antes do login
também importa).
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

MAX_EVENTS_PER_BATCH = 20
MAX_MESSAGE_LENGTH = 500
MAX_STACK_LENGTH = 4000
MAX_ROUTE_LENGTH = 300
MAX_SHORT_FIELD_LENGTH = 100

ClientLogLevel = Literal["error", "warning"]
# api_error = resposta HTTP de erro · network = sem resposta (offline/DNS/CORS) · unhandled =
# window.onerror/unhandledrejection · render = errorComponent do router · toast = erro local
# mostrado na tela sem passar pela API (validação, permissão do navegador).
ClientLogKind = Literal["api_error", "network", "unhandled", "render", "toast"]


class ClientLogEvent(BaseModel):
    level: ClientLogLevel = "error"
    kind: ClientLogKind
    title: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)
    message: str = Field(max_length=MAX_MESSAGE_LENGTH)
    stack: str | None = Field(default=None, max_length=MAX_STACK_LENGTH)
    # Só o path: a query string pode carregar busca digitada pelo usuário.
    route: str = Field(max_length=MAX_ROUTE_LENGTH)
    request_id: str | None = Field(default=None, max_length=MAX_SHORT_FIELD_LENGTH)
    status: int | None = None
    app_version: str | None = Field(default=None, max_length=MAX_SHORT_FIELD_LENGTH)
    occurred_at: dt.datetime


class ClientLogBatch(BaseModel):
    events: list[ClientLogEvent] = Field(min_length=1, max_length=MAX_EVENTS_PER_BATCH)

# --- services/observability/client_logs.py ---
"""Erros do navegador → log do backend (padrão da frota, 2026-10-22).

Cada evento vira UMA linha `client_error` no mesmo structlog/journald do backend, com
`source="frontend"`. O `client_request_id` é o `X-Request-ID` da resposta que falhou: buscar
por ele cai direto na linha do backend daquela chamada. Sem tabela de propósito — log de erro
é diagnóstico, e o destino dos logs da frota já é um só (`rules/logs.md`).
"""

import structlog

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


def write_client_logs(batch: ClientLogBatch, *, user_id: int | None, user_agent: str) -> None:
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

# --- routes/observability/client_logs.py ---
"""`POST /client-logs`: o navegador reporta os erros que mostrou (ou não pôde mostrar).

Auth OPCIONAL: o erro antes do login (tela de login, convite, vitrine) também importa, então a
rota é pública e só anota o `user_id` quando chega um Bearer válido. Sempre 204 — o front não
tem o que fazer com uma recusa, e erro aqui geraria mais um log de erro.
"""

from fastapi import APIRouter, Request, Response, status

from api.core.client_ip import client_ip
from api.core.exceptions_handler import BaseAPIExceptionError
from api.schemas.observability.client_logs import ClientLogBatch
from api.services.auth.permission_service import permission_service
from api.services.observability.client_logs import is_client_log_allowed, write_client_logs

router = APIRouter(tags=["Observability"])


async def optional_user_id(request: Request) -> int | None:
    try:
        context = await permission_service.check_authentication(request)
    except BaseAPIExceptionError:
        return None
    return context.get("user_id")


@router.post("/client-logs", status_code=status.HTTP_204_NO_CONTENT)
async def receive_client_logs(request: Request, batch: ClientLogBatch) -> Response:
    if await is_client_log_allowed(client_ip(request), len(batch.events)):
        write_client_logs(
            batch,
            user_id=await optional_user_id(request),
            user_agent=request.headers.get("user-agent", ""),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
