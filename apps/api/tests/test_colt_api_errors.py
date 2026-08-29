"""The structured error envelope (CLAUDE.md §25.4, §36)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from colt_api.errors import ColtError, ErrorCode, NotFoundError, PolicyDeniedError


def _assert_envelope(body: dict[str, object], code: ErrorCode) -> None:
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == code.value
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["request_id"], str) and error["request_id"]


def test_unknown_route_returns_the_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    _assert_envelope(response.json(), ErrorCode.NOT_FOUND)


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_code"),
    [
        (NotFoundError("Lead was not found."), 404, ErrorCode.NOT_FOUND),
        (PolicyDeniedError("Suppressed contact."), 403, ErrorCode.POLICY_DENIED),
        (ColtError(ErrorCode.CONFLICT, "Already sent."), 409, ErrorCode.CONFLICT),
        (ColtError(ErrorCode.RATE_LIMITED, "Slow down."), 429, ErrorCode.RATE_LIMITED),
        (ColtError(ErrorCode.TIMEOUT, "Upstream timed out."), 504, ErrorCode.TIMEOUT),
    ],
)
def test_colt_errors_map_to_their_status_and_code(
    app: FastAPI, exc: ColtError, expected_status: int, expected_code: ErrorCode
) -> None:
    @app.get("/api/v1/_raise")
    async def raise_it() -> None:
        raise exc

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/_raise")

    assert response.status_code == expected_status
    _assert_envelope(response.json(), expected_code)


def test_validation_failure_returns_a_422_envelope_with_details(app: FastAPI) -> None:
    class Payload(BaseModel):
        count: int

    @app.post("/api/v1/_validate")
    async def validate(payload: Payload) -> Payload:
        return payload

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/_validate", json={"count": "not-a-number"})

    assert response.status_code == 422
    body = response.json()
    _assert_envelope(body, ErrorCode.VALIDATION_ERROR)
    assert body["error"]["details"]["errors"], "validation details should describe the input"


def test_an_unhandled_exception_returns_500_without_leaking_internals(app: FastAPI) -> None:
    """§25.4: never leak stack traces or internal detail through API responses."""

    @app.get("/api/v1/_explode")
    async def explode() -> None:
        # A realistic-looking secret, deliberately fake: the point of the test is that it
        # must not reach the response.
        raise RuntimeError(
            "connection string postgresql://colt:hunter2@db/colt failed"  # pragma: allowlist secret
        )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/_explode")

    assert response.status_code == 500
    body = response.json()
    _assert_envelope(body, ErrorCode.INTERNAL_ERROR)

    raw = response.text
    assert "hunter2" not in raw
    assert "RuntimeError" not in raw
    assert "Traceback" not in raw
    assert "postgresql://" not in raw


def test_every_error_code_has_a_status_mapping() -> None:
    """A missing mapping would raise a KeyError while building an error response."""
    from colt_api.errors import _STATUS_BY_CODE

    assert set(_STATUS_BY_CODE) == set(ErrorCode)


def test_a_500_still_carries_the_caller_s_request_id(app: FastAPI) -> None:
    """Regression: Starlette handles unhandled exceptions outside our middleware, so the
    logging context has unwound by then. The ID must still reach the body and the header,
    because a 500 is the response an operator most needs to trace (CLAUDE.md §92)."""

    @app.get("/api/v1/_explode_traced")
    async def explode() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/_explode_traced", headers={"X-Request-ID": "req_trace_500"})

    assert response.status_code == 500
    assert response.json()["error"]["request_id"] == "req_trace_500"
    assert response.headers["X-Request-ID"] == "req_trace_500"
