from config.settings import settings


class MessagingConfig:
    """NATS broker configuration (client side)."""

    NATS_URL: str = settings.nats.url
    NATS_MAX_RECONNECT_ATTEMPTS: int = settings.nats.max_reconnect_attempts
    NATS_RECONNECT_TIME_WAIT: float = settings.nats.reconnect_time_wait
    NATS_CONNECT_TIMEOUT: float = settings.nats.connect_timeout


messaging_config = MessagingConfig()
