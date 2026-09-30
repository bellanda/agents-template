"""Auth context dependency — the single seam for request identity.

The agents API scopes thread history, usage accounting, and uploads by
``user_id``. This template ships an OPEN, header-based identity so it runs
standalone with no auth backend. Production deployments replace
``resolve_identity`` with real verification (decode a JWT from
``Authorization: Bearer``, load the user, check active/roles) — every route
depends on ``get_auth_context``, so it is a one-function swap.

Identity precedence (first non-empty wins):
    1. Authorization: Bearer <token>  → ``resolve_identity`` (stub: token IS the id)
    2. X-User-Id header
    3. ``user`` query param
    4. DEFAULT_USER_ID  ("default_user")

``client_id`` (optional sub-scope, e.g. an end-customer within a tenant) comes
from ``X-Client-Id`` header or ``client_id`` query param.

``tenant_id`` scopes tenant agent instructions (`agent_configs`) and per-tenant cost
(`agent_message_usage.tenant_id`). The template has no organizations: each user is its own
tenant. Apps set it to the organization id resolved from the verified token.
"""

from typing import Any

from fastapi import Request

DEFAULT_USER_ID = "default_user"
BEARER_PREFIX = "bearer "


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith(BEARER_PREFIX):
        token = header[len(BEARER_PREFIX) :].strip()
        return token or None
    return None


def resolve_identity(token: str) -> str | None:
    """Map a bearer token to a ``user_id``. STUB: treats the token AS the user_id.

    Replace with real verification: decode the JWT, return ``payload["sub"]``,
    raise ``AuthenticationError`` on invalid/expired tokens.
    """
    return token or None


async def get_auth_context(request: Request) -> dict[str, Any]:
    """Resolve the request identity. Open by default — never raises in the template."""
    token = _bearer_token(request)
    user_id = resolve_identity(token) if token else None
    if not user_id:
        user_id = (request.headers.get("x-user-id") or "").strip() or None
    if not user_id:
        user_id = (request.query_params.get("user") or "").strip() or None
    if not user_id:
        user_id = DEFAULT_USER_ID

    client_id = (request.headers.get("x-client-id") or "").strip() or None
    if not client_id:
        client_id = (request.query_params.get("client_id") or "").strip() or None

    return {"user_id": user_id, "client_id": client_id, "tenant_id": user_id, "roles": []}
