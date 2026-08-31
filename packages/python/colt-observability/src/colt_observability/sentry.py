"""Sentry error tracking — "where configured" (CLAUDE.md §68, Milestone 07): a no-op when no
DSN is set, not a hard dependency every environment must configure.
"""

from __future__ import annotations

import sentry_sdk


def configure_sentry(dsn: str | None, *, environment: str) -> None:
    """Initialize Sentry if `dsn` is non-empty; otherwise do nothing.

    Never raises on a missing DSN — local development and tests routinely run with none, and
    that must not be an error (§6.4: no real external side effects locally).
    """
    if not dsn:
        return
    sentry_sdk.init(dsn=dsn, environment=environment)
