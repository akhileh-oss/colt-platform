"""Correlation context binding (CLAUDE.md §35.1)."""

from __future__ import annotations

import pytest

from colt_observability import bind_log_context, get_log_context, get_request_id


def test_context_is_empty_by_default() -> None:
    assert get_log_context() == {}
    assert get_request_id() is None


def test_binding_exposes_fields_and_unbinds_on_exit() -> None:
    with bind_log_context(request_id="req_1", organization_id="org_1"):
        assert get_request_id() == "req_1"
        assert get_log_context() == {"request_id": "req_1", "organization_id": "org_1"}
    assert get_log_context() == {}


def test_nested_binding_merges_then_restores() -> None:
    with bind_log_context(request_id="req_1"):
        with bind_log_context(lead_id="lead_9"):
            assert get_log_context() == {"request_id": "req_1", "lead_id": "lead_9"}
        assert get_log_context() == {"request_id": "req_1"}


def test_none_values_are_dropped() -> None:
    with bind_log_context(request_id="req_1", user_id=None):
        assert get_log_context() == {"request_id": "req_1"}


def test_unknown_field_is_rejected() -> None:
    """A typo must fail loudly rather than create a field nothing searches for."""
    with pytest.raises(ValueError, match="reqest_id"), bind_log_context(reqest_id="req_1"):
        pass
