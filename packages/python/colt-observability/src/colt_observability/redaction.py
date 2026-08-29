"""Centralized log redaction (CLAUDE.md §93).

Redaction must not depend on every developer remembering it, so it is applied by the log
formatter to every record rather than at each call site.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

REDACTED: Final = "[REDACTED]"

#: A key is redacted when it *contains* one of these, case-insensitively, so `x_api_key`,
#: `ANTHROPIC_API_KEY` and `authorization` are all caught (CLAUDE.md §93).
SENSITIVE_KEY_PARTS: Final[frozenset[str]] = frozenset(
    {
        "authorization",
        "cookie",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "password",
        "passwd",
        "secret",
        "credential",
        "private_key",
        "session",
        "set-cookie",
    }
)

_MAX_DEPTH: Final = 6


def is_sensitive_key(key: str) -> bool:
    """Whether a mapping key names a value that must never be logged."""
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact(value: Any, _depth: int = 0) -> Any:
    """Return ``value`` with every sensitive mapping entry replaced by ``[REDACTED]``.

    Recurses through mappings and sequences. Structures deeper than ``_MAX_DEPTH`` are
    summarised rather than walked, so a pathological payload cannot stall logging.
    """
    if _depth >= _MAX_DEPTH:
        return "[TRUNCATED]"

    if isinstance(value, Mapping):
        return {
            key: (REDACTED if is_sensitive_key(str(key)) else redact(item, _depth + 1))
            for key, item in value.items()
        }

    # str and bytes are sequences; treat them as scalars.
    if isinstance(value, (str, bytes)):
        return value

    if isinstance(value, Sequence):
        return [redact(item, _depth + 1) for item in value]

    return value
