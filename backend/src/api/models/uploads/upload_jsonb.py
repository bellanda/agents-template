"""JSONB shapes and enums shared by the ``org_uploads`` / ``user_uploads`` tables.

- ``UploadKind`` mirrors the ``kind`` CHECK constraint.
- ``UploadVisibility`` mirrors the ``visibility`` CHECK constraint.
- ``UploadAcl`` lives inside ``UploadMetadata.acl`` — only consulted when
  ``visibility == 'tenant'``. Ambos campos opcionais.
- ``UploadMetadata`` is the typed wrapper for the ``metadata`` JSONB column.
  ``extra='allow'`` keeps it forward-compatible (B2 etag, EXIF, AI tags, etc.).

See ``uploads.md`` and skill ``uploads-storage``.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class UploadKind(StrEnum):
    LOGO = "logo"
    BANNER = "banner"
    AVATAR = "avatar"
    PHOTO = "photo"
    GALLERY_IMAGE = "gallery_image"
    DOCUMENT = "document"
    ATTACHMENT = "attachment"
    WHATSAPP_MEDIA = "whatsapp_media"
    EXPORT = "export"
    OTHER = "other"


class UploadVisibility(StrEnum):
    PUBLIC = "public"
    TENANT = "tenant"
    PRIVATE = "private"


class UploadAcl(BaseModel):
    """Granular ACL inside ``visibility='tenant'``.

    Both fields optional. Both empty → any member of the tenant has access.
    ``roles`` checked as set intersection with ``auth.roles``.
    ``user_ids`` checked as explicit membership.
    """

    roles: list[str] | None = None
    user_ids: list[str] | None = None


class UploadMetadata(BaseModel):
    """Typed wrapper for ``org_uploads``/``user_uploads`` ``metadata`` JSONB."""

    model_config = ConfigDict(extra="allow")

    # Object storage (BackBlaze B2 / S3-compatible)
    b2_etag: str | None = None
    b2_version_id: str | None = None

    # Image metadata
    exif: dict | None = None

    # ACL within tenant visibility
    acl: UploadAcl | None = None
