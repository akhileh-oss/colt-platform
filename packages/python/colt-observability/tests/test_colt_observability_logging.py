"""Structured JSON logging (CLAUDE.md §35, §93)."""

from __future__ import annotations

import json
import logging

import pytest

from colt_observability import JsonFormatter, bind_log_context, configure_logging, get_logger


def _format(record_factory_kwargs: dict[str, object]) -> dict[str, object]:
    formatter = JsonFormatter(service_name="colt-test")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="an event",
        args=(),
        exc_info=None,
    )
    for key, value in record_factory_kwargs.items():
        setattr(record, key, value)
    payload: dict[str, object] = json.loads(formatter.format(record))
    return payload


def test_record_is_valid_json_with_core_fields() -> None:
    payload = _format({})
    assert payload["message"] == "an event"
    assert payload["level"] == "INFO"
    assert payload["service"] == "colt-test"
    assert "timestamp" in payload


def test_extra_fields_are_included() -> None:
    payload = _format({"operation": "GET /live", "status": 200, "latency_ms": 1.5})
    assert payload["operation"] == "GET /live"
    assert payload["status"] == 200


def test_bound_context_is_included() -> None:
    with bind_log_context(request_id="req_abc", organization_id="org_1"):
        payload = _format({})
    assert payload["request_id"] == "req_abc"
    assert payload["organization_id"] == "org_1"


def test_sensitive_extra_fields_are_redacted() -> None:
    payload = _format({"api_key": "sk-ant-nope", "headers": {"Authorization": "Bearer nope"}})
    assert payload["api_key"] == "[REDACTED]"
    assert payload["headers"] == {"Authorization": "[REDACTED]"}
    assert "sk-ant-nope" not in json.dumps(payload)


def test_exception_is_summarised_without_a_traceback() -> None:
    """Tracebacks belong in the exception tracker, not in application logs (§25.4)."""
    formatter = JsonFormatter(service_name="colt-test")
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="t",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = json.loads(formatter.format(record))
    assert payload["exception_type"] == "ValueError"
    assert payload["exception_message"] == "boom"
    assert "Traceback" not in json.dumps(payload)


def test_configure_logging_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", service_name="colt-test")
    configure_logging(level="INFO", service_name="colt-test")
    get_logger("dup").info("once")
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert len(lines) == 1, "handlers were duplicated"
