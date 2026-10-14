from config.settings import settings


class CacheConfig:
    VALKEY_SOCK_PATH: str = settings.valkey.sock_path
    DEFAULT_TTL_SECONDS: int = settings.valkey.cache_default_ttl
    VALKEY_PASSWORD: str | None = (
        settings.valkey_password.get_secret_value()
        if settings.valkey_password is not None
        else None
    )


cache_config = CacheConfig()
