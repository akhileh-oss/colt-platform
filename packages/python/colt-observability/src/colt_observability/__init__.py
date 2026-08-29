"""Logging, tracing and metrics helpers built on OpenTelemetry."""

from colt_observability.context import (
    CONTEXT_FIELDS,
    bind_log_context,
    get_log_context,
    get_request_id,
)
from colt_observability.logging import JsonFormatter, configure_logging, get_logger
from colt_observability.redaction import REDACTED, SENSITIVE_KEY_PARTS, is_sensitive_key, redact

__version__ = "0.1.0"

__all__ = [
    "CONTEXT_FIELDS",
    "REDACTED",
    "SENSITIVE_KEY_PARTS",
    "JsonFormatter",
    "__version__",
    "bind_log_context",
    "configure_logging",
    "get_log_context",
    "get_logger",
    "get_request_id",
    "is_sensitive_key",
    "redact",
]
