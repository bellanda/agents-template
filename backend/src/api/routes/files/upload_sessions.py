"""Template adapter for the canonical chunked-upload module (``services/uploads/upload_sessions``).

Only auth lives here: the user key is the authenticated user id. It authenticates by itself
(through ``get_auth_context``, the template's single identity seam) because FastAPI resolves
dependencies BEFORE the route body runs, and the staged-file dependency must already know the user
to find the session. When an app replaces ``get_auth_context`` with real token verification this
adapter follows automatically; no change needed here.
"""

from fastapi import Request

from api.services.auth import get_auth_context
from api.services.uploads.upload_sessions import (
    build_upload_sessions_router,
    make_staged_or_direct_file,
)


async def upload_session_user_key(request: Request) -> str:
    context = await get_auth_context(request)
    return str(context["user_id"])


router = build_upload_sessions_router(upload_session_user_key)

# `file` (multipart) or `file_upload_id` (staged chunks). Use `optional_staged_file` when the
# file is optional.
staged_file = make_staged_or_direct_file(upload_session_user_key)
optional_staged_file = make_staged_or_direct_file(upload_session_user_key, required=False)
