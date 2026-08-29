"""Structured JSON application logging (CLAUDE.md §3.6, §35).

Every record is emitted as one JSON object, carries whatever correlation fields are bound
(§35.1), and is passed through redaction (§93) before serialisation.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, Final

from colt_observability.context import get_log_context
from colt_observability.redaction import redact

#: Attributes present on every LogRecord; anything else a caller passes via `extra` is
#: treated as a structured field and included in the output.
_STANDARD_RECORD_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render a log record as a single redacted JSON object."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self._service_name,
            "message": record.getMessage(),
        }

        payload.update(get_log_context())

        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            # The type and message, never the traceback: tracebacks belong in the exception
            # tracker, not in application logs that may be widely readable (§25.4).
            exc_type, exc_value, _ = record.exc_info
            if exc_type is not None:
                payload["exception_type"] = exc_type.__name__
                payload["exception_message"] = str(exc_value)

        return json.dumps(redact(payload), default=str, separators=(",", ":"))


def configure_logging(*, level: str = "INFO", service_name: str = "colt") -> None:
    """Install JSON logging on the root logger.

    Idempotent: existing handlers are replaced, so calling this twice does not duplicate output.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service_name=service_name))

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())

    # uvicorn installs its own handlers; route them through ours instead of duplicating lines.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger. Use ``__name__`` at the call site."""
    return logging.getLogger(name)
