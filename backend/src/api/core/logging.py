"""Logging stack — structlog + stdlib + orjson.

NDJSON in prod, ConsoleRenderer in dev (TTY-aware), QueueHandler async-safe.
Third-party libs (asyncpg, granian, uvicorn) flow through the same
ProcessorFormatter, so every line — app or lib — has the same shape.

Config comes from `settings.logging` (config/app/{env}.yaml): service_name, app_env, level,
format ("" = auto | json | console) and per-lib levels (`level_asyncpg`). The first three feed
every log line, so they are not optional.

See `.claude/rules/logging.md` for the full spec.
"""

import logging
import logging.config
import queue
import sys
from logging.handlers import QueueHandler, QueueListener
from typing import Any

import orjson
import structlog

from config.settings import settings

LOG_QUEUE_MAXSIZE = -1  # unbounded; level filtering happens before enqueue
THIRD_PARTY_DEFAULTS = {
    "asyncpg": "WARNING",
    "uvicorn.access": "INFO",
    "uvicorn.error": "INFO",
    "granian.access": "INFO",
    "granian": "INFO",
    "httpx": "WARNING",
}

listener: QueueListener | None = None


class _RawQueueHandler(QueueHandler):
    """QueueHandler that doesn't stringify the record before enqueueing.

    structlog's ProcessorFormatter expects `record.msg` to remain a dict.
    The default `QueueHandler.prepare` calls `record.getMessage()` which
    coerces it to str, breaking the formatter on the listener side.
    """

    def prepare(self, record):
        return record


class LogConfig:
    SERVICE_NAME: str = settings.logging.service_name
    APP_ENV: str = settings.logging.app_env
    LOG_LEVEL: str = settings.logging.level.upper()
    LOG_FORMAT: str = (settings.logging.format or "auto").lower()

    @classmethod
    def is_json(cls) -> bool:
        if cls.LOG_FORMAT == "json":
            return True
        if cls.LOG_FORMAT == "console":
            return False
        return not sys.stderr.isatty()


def _orjson_dumps(obj: Any, default: Any = None) -> str:
    return orjson.dumps(obj, default=default).decode("utf-8")


def _add_service_context(_logger: Any, _name: str, event_dict: dict) -> dict:
    event_dict.setdefault("service", LogConfig.SERVICE_NAME)
    event_dict.setdefault("env", LogConfig.APP_ENV)
    return event_dict


def _resolve_exc_info(_logger: Any, _name: str, event_dict: dict) -> dict:
    """Resolve `exc_info=True` to a real (type, value, tb) tuple.

    Required because the QueueListener runs the renderer on a different
    thread, where `sys.exc_info()` no longer points at the original exception.
    Without this, ConsoleRenderer/JSON path silently lose the traceback.
    """
    exc = event_dict.get("exc_info")
    if exc is True:
        event_dict["exc_info"] = sys.exc_info()
    return event_dict


def _shared_processors() -> list:
    """Processors run for BOTH structlog and stdlib log entries (third-party).

    `format_exc_info` is added only in JSON mode — ConsoleRenderer formats
    tracebacks itself and emits a UserWarning if it sees pre-formatted ones.
    """
    base = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        _add_service_context,
        _resolve_exc_info,
        structlog.processors.StackInfoRenderer(),
    ]
    if LogConfig.is_json():
        base.append(structlog.processors.format_exc_info)
    return base


def _final_renderer() -> Any:
    if LogConfig.is_json():
        return structlog.processors.JSONRenderer(serializer=_orjson_dumps)
    return structlog.dev.ConsoleRenderer(colors=True, sort_keys=False)


def setup_logging() -> None:
    """Configure stdlib logging + structlog. Idempotent. Starts QueueListener."""
    global listener

    shared = _shared_processors()
    renderer = _final_renderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    log_queue: queue.Queue = queue.Queue(LOG_QUEUE_MAXSIZE)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)

    if listener is not None:
        listener.stop()
    listener = QueueListener(log_queue, stream_handler, respect_handler_level=True)

    queue_handler = _RawQueueHandler(log_queue)

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(queue_handler)
    root.setLevel(LogConfig.LOG_LEVEL)

    for name, default_level in THIRD_PARTY_DEFAULTS.items():
        # settings.logging exposes `level_<lib>` (only `level_asyncpg` today); other libs
        # keep their default. Add a field to LoggingSettings + the yamls to tune one.
        yaml_attr = f"level_{name.lower().replace('.', '_')}"
        level = getattr(settings.logging, yaml_attr, default_level)
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = True

    structlog.configure(
        processors=[
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, LogConfig.LOG_LEVEL, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    listener.start()


def shutdown_logging() -> None:
    """Stop QueueListener gracefully. Call from FastAPI lifespan shutdown."""
    global listener
    if listener is not None:
        listener.stop()
        listener = None


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)


def bind_request_id(request_id: str) -> None:
    structlog.contextvars.bind_contextvars(request_id=request_id)


def clear_request_id() -> None:
    structlog.contextvars.clear_contextvars()


def dict_config_for_servers() -> dict:
    """Return a dictConfig usable by Granian `--log-config` and uvicorn `log_config=`.

    Third-party server loggers send LogRecords to the root logger, which has the
    QueueHandler installed by setup_logging(). This dict only exists to silence
    the server's "no handlers" complaints when it inspects the config; the
    actual handler chain is set up imperatively in setup_logging().
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"passthrough": {"format": "%(message)s"}},
        "handlers": {
            "default": {
                "class": "logging.NullHandler",
            },
        },
        "loggers": {
            name: {"level": level, "propagate": True}
            for name, level in THIRD_PARTY_DEFAULTS.items()
        },
        "root": {"level": LogConfig.LOG_LEVEL, "handlers": []},
    }
