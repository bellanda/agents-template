"""asyncpg repository for the ``user_uploads`` table (user-owned uploads).

Caller supplies the connection. Repo returns ``dict`` / ``list[dict]`` / scalar.

See rule ``uploads.md`` and skill ``uploads-storage``.
"""

import datetime as dt
from uuid import UUID

from asyncpg.connection import Connection

from api.models.uploads.user_upload import UserUpload


class UserUploadRepository:
    async def create(self, conn: Connection, file: UserUpload) -> dict:
        row = await conn.fetchrow(
            """
            INSERT INTO user_uploads (
                owner_user_id, entity_type, entity_id, kind,
                url, filename, mime_type, size_bytes, width, height,
                visibility, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING *
            """,
            file.owner_user_id,
            file.entity_type,
            file.entity_id,
            file.kind.value,
            file.url,
            file.filename,
            file.mime_type,
            file.size_bytes,
            file.width,
            file.height,
            file.visibility.value,
            file.metadata.model_dump(exclude_none=False),
        )
        return dict(row)

    async def update(self, conn: Connection, file_id: UUID, data: dict) -> dict | None:
        row = await conn.fetchrow(
            """
            UPDATE user_uploads
            SET
                entity_type = COALESCE($2, entity_type),
                entity_id   = COALESCE($3, entity_id),
                kind        = COALESCE($4, kind),
                url         = COALESCE($5, url),
                filename    = COALESCE($6, filename),
                mime_type   = COALESCE($7, mime_type),
                size_bytes  = COALESCE($8, size_bytes),
                width       = COALESCE($9, width),
                height      = COALESCE($10, height),
                visibility  = COALESCE($11, visibility),
                metadata    = COALESCE($12, metadata)
            WHERE id = $1
            RETURNING *
            """,
            file_id,
            data.get("entity_type"),
            data.get("entity_id"),
            data.get("kind"),
            data.get("url"),
            data.get("filename"),
            data.get("mime_type"),
            data.get("size_bytes"),
            data.get("width"),
            data.get("height"),
            data.get("visibility"),
            data.get("metadata"),
        )
        return dict(row) if row else None

    async def find_by_id(self, conn: Connection, file_id: UUID) -> dict | None:
        row = await conn.fetchrow(
            "SELECT * FROM user_uploads WHERE id = $1 AND deleted_at IS NULL",
            file_id,
        )
        return dict(row) if row else None

    async def find_by_url(self, conn: Connection, url: str) -> dict | None:
        row = await conn.fetchrow(
            "SELECT * FROM user_uploads WHERE url = $1 AND deleted_at IS NULL",
            url,
        )
        return dict(row) if row else None

    async def find_by_entity(
        self,
        conn: Connection,
        entity_type: str,
        entity_id: str,
        kind: str | None = None,
    ) -> list[dict]:
        if kind is None:
            rows = await conn.fetch(
                """
                SELECT * FROM user_uploads
                WHERE entity_type = $1 AND entity_id = $2 AND deleted_at IS NULL
                ORDER BY created_at
                """,
                entity_type,
                entity_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT * FROM user_uploads
                WHERE entity_type = $1 AND entity_id = $2 AND kind = $3
                  AND deleted_at IS NULL
                ORDER BY created_at
                """,
                entity_type,
                entity_id,
                kind,
            )
        return [dict(r) for r in rows]

    async def soft_delete(self, conn: Connection, file_id: UUID) -> bool:
        deleted = await conn.fetchval(
            """
            UPDATE user_uploads
            SET deleted_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            RETURNING id
            """,
            file_id,
        )
        return deleted is not None

    async def hard_delete(self, conn: Connection, file_id: UUID) -> bool:
        deleted = await conn.fetchval(
            "DELETE FROM user_uploads WHERE id = $1 RETURNING id",
            file_id,
        )
        return deleted is not None

    async def find_orphans_for_user(
        self,
        conn: Connection,
        owner_user_id: str,
        older_than: dt.datetime,
    ) -> list[dict]:
        """Soft-deleted rows for a user created before ``older_than``. Background cleanup."""
        rows = await conn.fetch(
            """
            SELECT * FROM user_uploads
            WHERE owner_user_id = $1
              AND created_at < $2
              AND deleted_at IS NOT NULL
            ORDER BY created_at
            """,
            owner_user_id,
            older_than,
        )
        return [dict(r) for r in rows]


user_upload_repository = UserUploadRepository()
