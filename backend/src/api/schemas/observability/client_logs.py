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
