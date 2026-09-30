"""External-service credentials and endpoints, flattened from `settings` (shim: no logic here).

Same attribute names as the product apps' `config/integrations.py`, so `core/agents` (copied
by the sync script) works unchanged in any of them. Secrets come from `.env`, the rest from
`config/app/{env}.yaml > openrouter:`.
"""

from config.settings import settings


def _opt_secret(value):
    return value.get_secret_value() if value else None


class IntegrationsConfig:
    """AI providers: OpenRouter (all chat) + Groq (audio transcription only)."""

    GROQ_API_KEY: str | None = _opt_secret(settings.groq_api_key)
    OPENROUTER_API_KEY: str | None = _opt_secret(settings.openrouter_api_key)
    OPENROUTER_API_BASE: str = settings.openrouter.api_base
    OPENROUTER_SITE_URL: str = settings.openrouter.site_url
    OPENROUTER_APP_TITLE: str = settings.openrouter.app_title


integrations_config = IntegrationsConfig()
