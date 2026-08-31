"""Logging, tracing and metrics helpers built on OpenTelemetry."""

from colt_observability.context import (
    CONTEXT_FIELDS,
    bind_log_context,
    get_log_context,
    get_request_id,
)
from colt_observability.logging import JsonFormatter, configure_logging, get_logger
from colt_observability.metrics import configure_metrics, get_meter
from colt_observability.redaction import REDACTED, SENSITIVE_KEY_PARTS, is_sensitive_key, redact
from colt_observability.sentry import configure_sentry
from colt_observability.tracing import configure_tracing, get_tracer, instrument_sqlalchemy

__version__ = "0.1.0"

__all__ = [
    "CONTEXT_FIELDS",
    "REDACTED",
    "SENSITIVE_KEY_PARTS",
    "JsonFormatter",
    "__version__",
    "bind_log_context",
    "configure_logging",
    "configure_metrics",
    "configure_sentry",
    "configure_tracing",
    "get_log_context",
    "get_logger",
    "get_meter",
    "get_request_id",
    "get_tracer",
    "instrument_sqlalchemy",
    "is_sensitive_key",
    "redact",
]
