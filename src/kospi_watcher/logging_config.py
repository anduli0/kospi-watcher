"""Structured logging (structlog) with secret redaction.

Named ``logging_config`` rather than ``logging`` to avoid shadowing the stdlib
module. Emits JSON in prod and a console renderer in dev. A redaction processor
scrubs any key that looks like a credential, so secrets never reach the logs
(security principle §14.3).
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import EventDict, WrappedLogger

_SENSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "secret",
    "password",
    "passwd",
    "token",
    "api_key",
    "apikey",
    "app_key",
    "appkey",
    "account_number",
    "credential",
    "authorization",
)

_REDACTED = "***REDACTED***"


def _redact_secrets(
    _logger: WrappedLogger, _method: str, event_dict: EventDict
) -> EventDict:
    """structlog processor that masks credential-looking keys."""
    for key in list(event_dict.keys()):
        lowered = key.lower()
        if any(token in lowered for token in _SENSITIVE_SUBSTRINGS):
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(*, json_logs: bool = True, level: str = "INFO") -> None:
    """Configure structlog once at process start."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_secrets,
        structlog.processors.StackInfoRenderer(),
    ]
    if json_logs:
        processors.append(structlog.processors.format_exc_info)
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
