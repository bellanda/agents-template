"""`POST /client-logs`: the browser reports the errors it showed (or could not show).

Public route: errors before login also matter. The template identity is open and header-based
(`services/auth.py`), so `user_id` is only annotated when an `Authorization: Bearer` header
arrives; apps with real token verification should make `optional_user_id` swallow the auth
failure and return None for invalid tokens. Always 204: the frontend can do nothing with a
refusal, and an error here would only generate one more error log.
"""

from fastapi import APIRouter, Request, Response, status

from api.schemas.observability.client_logs import ClientLogBatch
from api.services.auth import get_auth_context
from api.services.observability.client_logs import (
    client_ip_from_request,
    is_client_log_allowed,
    write_client_logs,
)

router = APIRouter(tags=["Observability"])


async def optional_user_id(request: Request) -> str | None:
    if not request.headers.get("authorization"):
        return None
    context = await get_auth_context(request)
    return context.get("user_id")


@router.post("/client-logs", status_code=status.HTTP_204_NO_CONTENT)
async def receive_client_logs(request: Request, batch: ClientLogBatch) -> Response:
    if await is_client_log_allowed(client_ip_from_request(request), len(batch.events)):
        write_client_logs(
            batch,
            user_id=await optional_user_id(request),
            user_agent=request.headers.get("user-agent", ""),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
