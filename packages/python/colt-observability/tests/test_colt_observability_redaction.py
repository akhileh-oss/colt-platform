"""Redaction must be automatic and total (CLAUDE.md §93)."""

from __future__ import annotations

import pytest

from colt_observability import REDACTED, is_sensitive_key, redact


@pytest.mark.parametrize(
    "key",
    [
        "authorization",
        "Authorization",
        "cookie",
        "Set-Cookie",
        "api_key",
        "X_API_KEY",
        "apiKey",
        "access_token",
        "refresh_token",
        "client_secret",
        "password",
        "ANTHROPIC_API_KEY",
        "db_password",
        "session_id",
        "private_key",
    ],
)
def test_sensitive_keys_are_recognised(key: str) -> None:
    assert is_sensitive_key(key)


@pytest.mark.parametrize("key", ["user_id", "organization_id", "status", "latency_ms", "operation"])
def test_ordinary_keys_are_not_redacted(key: str) -> None:
    assert not is_sensitive_key(key)


def test_redaction_replaces_values_and_keeps_structure() -> None:
    payload = {"user_id": "u1", "api_key": "sk-ant-secret", "nested": {"password": "hunter2"}}
    assert redact(payload) == {
        "user_id": "u1",
        "api_key": REDACTED,
        "nested": {"password": REDACTED},
    }


def test_redaction_walks_sequences() -> None:
    result = redact({"items": [{"token": "a", "access_token": "b"}]})
    assert result == {"items": [{"token": "a", "access_token": REDACTED}]}


def test_strings_are_not_treated_as_sequences() -> None:
    assert redact({"message": "hello"}) == {"message": "hello"}


def test_deeply_nested_structures_are_truncated_not_walked_forever() -> None:
    payload: dict[str, object] = {"k": "v"}
    for _ in range(20):
        payload = {"k": payload}
    assert "[TRUNCATED]" in str(redact(payload))
