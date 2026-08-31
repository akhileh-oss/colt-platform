"""`configure_sentry` — a no-op without a DSN (CLAUDE.md §68, Milestone 07: "where configured")."""

from __future__ import annotations

import sentry_sdk

from colt_observability import configure_sentry


def test_no_dsn_leaves_sentry_uninitialized() -> None:
    configure_sentry(None, environment="test")
    assert sentry_sdk.get_client().is_active() is False


def test_blank_dsn_leaves_sentry_uninitialized() -> None:
    configure_sentry("", environment="test")
    assert sentry_sdk.get_client().is_active() is False
