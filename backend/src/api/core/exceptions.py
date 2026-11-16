"""API exceptions in the FLEET vocabulary (kailos/akmeo/emporion/promoservice/nexarena/optimuslar).

Drift 2026-11-13 (drift-backend-07): the template used to ship `NotFoundError` while every app
names the same thing `DoesNotExistError` (and has `ConflictError`, `RateLimitError`,
`BaseAPIExceptionError`). `sync_agents_to_another_fastapi_project.py` overwrites routes/services
of the agents layer but copies this file only when missing, so a synced app crashed on
`ImportError` at boot. Same names and the same `detail=` keyword as the apps now, so the synced
agent code imports cleanly in both. ALWAYS pass `detail=` by keyword: in the apps the first
positional parameter of `BaseAPIExceptionError` is `type`, not the message.

These subclass FastAPI's ``HTTPException`` so they are handled natively (no custom handler
needed in the template); the apps' own classes render RFC 7807 bodies instead. ``config/uploads.py``
raises ``BadRequestError`` for invalid MIME/size/corrupt-image per rule ``uploads.md``.
"""

from fastapi import HTTPException, status


class BaseAPIExceptionError(HTTPException):
    STATUS: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    DETAIL: str = "Ocorreu um erro inesperado."

    def __init__(self, *, detail: str | None = None) -> None:
        super().__init__(status_code=self.STATUS, detail=detail or self.DETAIL)


class AuthenticationError(BaseAPIExceptionError):
    STATUS = status.HTTP_401_UNAUTHORIZED
    DETAIL = "Falha na autenticação"


class BadRequestError(BaseAPIExceptionError):
    STATUS = status.HTTP_400_BAD_REQUEST
    DETAIL = "Requisição inválida"


class ForbiddenError(BaseAPIExceptionError):
    STATUS = status.HTTP_403_FORBIDDEN
    DETAIL = "Acesso negado"


class DoesNotExistError(BaseAPIExceptionError):
    STATUS = status.HTTP_404_NOT_FOUND
    DETAIL = "Não encontrado"


class ConflictError(BaseAPIExceptionError):
    STATUS = status.HTTP_409_CONFLICT
    DETAIL = "Conflito"


class RateLimitError(BaseAPIExceptionError):
    STATUS = status.HTTP_429_TOO_MANY_REQUESTS
    DETAIL = "Muitas requisições. Tente novamente mais tarde."
