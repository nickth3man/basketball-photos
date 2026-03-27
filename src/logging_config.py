"""
Structlog configuration for console (development) and JSONL (production) output.

Provides centralized logging configuration with graceful fallback to standard
logging if structlog is not available.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from structlog.types import BoundLogger, Processor


class FallbackLogger:
    """Wrapper around standard logging that accepts kwargs like structlog."""

    def __init__(self, name: Optional[str] = None):
        self._logger = logging.getLogger(name)
        self._level = logging.INFO

    def _format_message(self, event: str, **kwargs) -> str:
        if kwargs:
            formatted_kwargs = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
            return f"{event} | {formatted_kwargs}"
        return event

    def _log(self, level: int, event: str, **kwargs) -> None:
        self._logger.log(level, self._format_message(event, **kwargs))

    def debug(self, event: str, **kwargs) -> None:
        self._log(logging.DEBUG, event, **kwargs)

    def info(self, event: str, **kwargs) -> None:
        self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs) -> None:
        self._log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs) -> None:
        self._log(logging.ERROR, event, **kwargs)

    def critical(self, event: str, **kwargs) -> None:
        self._log(logging.CRITICAL, event, **kwargs)

    def exception(self, event: str, **kwargs) -> None:
        self._logger.exception(self._format_message(event, **kwargs))

    def bind(self, **kwargs) -> "FallbackLogger":
        return self

    def unbind(self, *keys: str) -> "FallbackLogger":
        return self

    def try_unbind(self, *keys: str) -> "FallbackLogger":
        return self

    def new(self, **kwargs) -> "FallbackLogger":
        return self


LoggerType = Union["BoundLogger", FallbackLogger]


try:
    import structlog
    from structlog.dev import ConsoleRenderer
    from structlog.processors import (
        CallsiteParameter,
        CallsiteParameterAdder,
        add_log_level,
        add_logger_name,
    )
    from structlog.types import BoundLogger, Processor

    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False
    structlog = None  # type: ignore[misc,assignment]
    BoundLogger = FallbackLogger  # type: ignore[misc,assignment]
    Processor = Any  # type: ignore[misc,assignment]

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "console"

_configured = False
_current_level = DEFAULT_LOG_LEVEL
_current_format = DEFAULT_LOG_FORMAT
_current_file: Optional[str] = None


def _get_log_level(level: str) -> int:
    """Convert string log level to logging constant."""
    level_upper = level.upper()
    if level_upper not in VALID_LOG_LEVELS:
        raise ValueError(
            f"Invalid log level '{level}'. Must be one of: {', '.join(sorted(VALID_LOG_LEVELS))}"
        )
    return getattr(logging, level_upper)


def _get_shared_processors() -> list[Processor]:
    """Return shared processors for both console and JSONL output."""
    if not HAS_STRUCTLOG:
        return []

    return [
        structlog.contextvars.merge_contextvars,
        add_log_level,
        add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        CallsiteParameterAdder(
            [
                CallsiteParameter.FILENAME,
                CallsiteParameter.LINENO,
                CallsiteParameter.FUNC_NAME,
            ]
        ),
    ]


def _get_json_renderer() -> Processor:
    """Return JSON renderer with orjson if available, fallback to stdlib json."""
    if not HAS_STRUCTLOG:
        return lambda _, __, event_dict: event_dict

    try:
        import orjson

        def json_renderer(
            logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
        ) -> bytes:
            event_dict = structlog.processors.dict_tracebacks(
                logger, method_name, event_dict
            )
            return orjson.dumps(event_dict, default=str)

        return json_renderer
    except ImportError:
        import json

        def json_renderer(
            logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
        ) -> str:
            event_dict = structlog.processors.dict_tracebacks(
                logger, method_name, event_dict
            )
            return json.dumps(event_dict, default=str)

        return json_renderer


def _configure_file_handler(log_file: str, level: int) -> logging.FileHandler:
    """Configure and return a file handler for JSONL output."""
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def configure_logging(
    log_level: str = DEFAULT_LOG_LEVEL,
    log_format: str = DEFAULT_LOG_FORMAT,
    log_file: Optional[str] = None,
) -> None:
    """
    Configure structlog for console (development) or JSONL (production) output.

    Args:
        log_level: Log level as string. One of: DEBUG, INFO, WARNING, ERROR, CRITICAL.
                   Default: "INFO"
        log_format: Output format. One of: "console" (pretty, colored) or "jsonl"
                    (structured JSON). Default: "console"
        log_file: Path to log file for JSONL output. Only used when log_format="jsonl".
                  Default: None

    Raises:
        ValueError: If log_level or log_format is invalid.

    Example:
        configure_logging("INFO", "console")
        configure_logging("INFO", "jsonl", "app.log")
    """
    global _configured, _current_level, _current_format, _current_file

    log_level_upper = log_level.upper()
    if log_level_upper not in VALID_LOG_LEVELS:
        raise ValueError(
            f"Invalid log level '{log_level}'. Must be one of: {', '.join(sorted(VALID_LOG_LEVELS))}"
        )

    log_format_lower = log_format.lower()
    if log_format_lower not in ("console", "jsonl"):
        raise ValueError(
            f"Invalid log format '{log_format}'. Must be 'console' or 'jsonl'"
        )

    _current_level = log_level_upper
    _current_format = log_format_lower
    _current_file = log_file
    _configured = True

    level_int = _get_log_level(log_level_upper)

    if not HAS_STRUCTLOG:
        logging.basicConfig(
            level=level_int,
            format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        return

    shared_processors = _get_shared_processors()

    if log_format_lower == "console":
        processors: list[Processor] = shared_processors + [ConsoleRenderer(colors=True)]
    else:
        processors = shared_processors + [_get_json_renderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level_int),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    if log_format_lower == "jsonl" and log_file:
        root_logger = logging.getLogger()
        root_logger.setLevel(level_int)
        root_logger.handlers.clear()

        file_handler = _configure_file_handler(log_file, level_int)
        root_logger.addHandler(file_handler)

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(level_int),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(
                output=open(log_file, "a", encoding="utf-8")
            ),
            cache_logger_on_first_use=True,
        )
    else:
        root_logger = logging.getLogger()
        root_logger.setLevel(level_int)
        root_logger.handlers.clear()

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level_int)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(console_handler)


def get_logger(name: Optional[str] = None) -> LoggerType:
    """
    Get a configured structlog logger.

    Args:
        name: Optional logger name. If not provided, uses the calling module's name.

    Returns:
        A BoundLogger instance (or FallbackLogger if structlog not available).

    Example:
        log = get_logger(__name__)
        log.info("analysis_started", photo_path="test.jpg")
        log.error("analysis_failed", error="disk full", photo_path="test.jpg")
    """
    if not HAS_STRUCTLOG:
        return FallbackLogger(name)

    if not _configured:
        configure_logging()

    return structlog.get_logger(name)


def set_log_level(level: str) -> None:
    """
    Dynamically adjust the log level at runtime.

    Args:
        level: New log level as string. One of: DEBUG, INFO, WARNING, ERROR, CRITICAL.

    Raises:
        ValueError: If log level is invalid.

    Example:
        set_log_level("DEBUG")
        set_log_level("WARNING")
    """
    global _current_level

    level_upper = level.upper()
    if level_upper not in VALID_LOG_LEVELS:
        raise ValueError(
            f"Invalid log level '{level}'. Must be one of: {', '.join(sorted(VALID_LOG_LEVELS))}"
        )

    _current_level = level_upper
    level_int = _get_log_level(level_upper)

    logging.getLogger().setLevel(level_int)

    if HAS_STRUCTLOG:
        configure_logging(
            log_level=_current_level,
            log_format=_current_format,
            log_file=_current_file,
        )


def is_configured() -> bool:
    """Check if logging has been configured."""
    return _configured


def get_current_level() -> str:
    """Get the current log level."""
    return _current_level


def get_current_format() -> str:
    """Get the current log format."""
    return _current_format
