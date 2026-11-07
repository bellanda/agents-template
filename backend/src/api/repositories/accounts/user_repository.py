"""asyncpg repository for ``users`` (identidade do template + ``ui_preferences``).

Caller supplies the connection. Repo returns ``dict`` / ``list[dict]`` / scalar.
"""

from asyncpg.connection import Connection


class UserRepository:
    async def get_ui_preferences(self, conn: Connection, user_id: str) -> dict:
        """Preferências da pessoa; ``{}`` se ela ainda não gravou nenhuma (sem linha)."""
        value = await conn.fetchval("SELECT ui_preferences FROM users WHERE id = $1", user_id)
        return value or {}

    async def set_app_style(self, conn: Connection, user_id: str, app_style: str) -> dict:
        """Grava ``ui_preferences->app_style`` sem tocar nas outras chaves (upsert).

        O template cria a linha na primeira escolha; num app com login real a linha já existe.
        """
        return await conn.fetchval(
            """
            INSERT INTO users (id, ui_preferences)
            VALUES ($1, jsonb_build_object('app_style', $2::text))
            ON CONFLICT (id) DO UPDATE
            SET ui_preferences = jsonb_set(
                users.ui_preferences, '{app_style}', to_jsonb($2::text), true
            )
            RETURNING ui_preferences
            """,
            user_id,
            app_style,
        )


user_repository = UserRepository()
