"""Per-request logging context (CLAUDE.md §35.1).

Correlation identifiers are carried in a context variable rather than threaded through every
call, so that any log record emitted while handling a request carries them automatically.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Final

#: The correlation fields CLAUDE.md §35.1 requires, where applicable.
CONTEXT_FIELDS: Final[tuple[str, ...]] = (
    "request_id",
    "trace_id",
    "organization_id",
    "user_id",
    "workflow_id",
    "workflow_run_id",
    "agent_run_id",
    "lead_id",
    "campaign_id",
)

# Default is None rather than {}: a shared mutable default is a footgun even when every
# reader copies it today.
_log_context: ContextVar[dict[str, str] | None] = ContextVar("colt_log_context", default=None)


def get_log_context() -> dict[str, str]:
    """Return the correlation fields currently bound."""
    return dict(_log_context.get() or {})


def get_request_id() -> str | None:
    """Return the current request ID, if one is bound."""
    return (_log_context.get() or {}).get("request_id")


@contextmanager
def bind_log_context(**fields: str | None) -> Iterator[None]:
    """Bind correlation fields for the duration of the block.

    Unknown field names are rejected rather than silently accepted, so a typo cannot quietly
    produce a log field nothing searches for. ``None`` values are dropped.
    """
    unknown = set(fields) - set(CONTEXT_FIELDS)
    if unknown:
        raise ValueError(
            f"Unknown log context field(s): {', '.join(sorted(unknown))}. "
            f"Known fields: {', '.join(CONTEXT_FIELDS)}."
        )

    merged = dict(_log_context.get() or {})
    merged.update({key: value for key, value in fields.items() if value is not None})
    token = _log_context.set(merged)
    try:
        yield
    finally:
        _log_context.reset(token)
