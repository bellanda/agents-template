"""Pydantic mirror of the ``user_uploads`` table (user-owned uploads).

Single source of truth for every user-owned uploaded asset. Entities reference
rows here via FK (``{entity}.{kind}_id``) or join tables (``{entity}_files``).
``owner_user_id`` is always present; there is no ``organization_id``.

The template's identity is a string (no ``users`` table — see ``chat_history``),
so ``owner_user_id`` is ``str`` here. Projects with a real ``users`` table use an
``int``/``UUID`` FK instead. See rule ``uploads.md`` and skill ``uploads-storage``.
"""

import datetime as dt
from uuid import UUID

from pydantic import BaseModel, Field

from api.models.uploads.upload_jsonb import (
    UploadKind,
    UploadMetadata,
    UploadVisibility,
)


class UserUpload(BaseModel):
    id: UUID | None = None
    owner_user_id: str = Field(..., max_length=255)
    entity_type: str = Field(..., max_length=64)
    entity_id: str | None = None
    kind: UploadKind
    url: str
    filename: str
    mime_type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    visibility: UploadVisibility = UploadVisibility.PUBLIC
    metadata: UploadMetadata = Field(default_factory=UploadMetadata)
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None
    deleted_at: dt.datetime | None = None
