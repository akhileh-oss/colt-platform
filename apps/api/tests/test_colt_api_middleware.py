"""Security headers, CORS and request size limits (CLAUDE.md §40)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from colt_api.app import create_app
from colt_api.middleware import SECURITY_HEADERS
from colt_config import Settings


@pytest.mark.parametrize("header", sorted(SECURITY_HEADERS))
def test_security_headers_are_present(client: TestClient, header: str) -> None:
    assert client.get("/live").headers[header] == SECURITY_HEADERS[header]


def test_hsts_is_not_set_over_plain_http() -> None:
    """Set at the TLS terminator; sending it locally would poison the developer's browser."""
    assert "Strict-Transport-Security" not in SECURITY_HEADERS


def test_cors_allows_the_configured_origin(client: TestClient) -> None:
    response = client.get("/live", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_an_unconfigured_origin(client: TestClient) -> None:
    response = client.get("/live", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_exposes_the_request_id_header(client: TestClient) -> None:
    """The browser client needs to read it to report a traceable failure."""
    response = client.get("/live", headers={"Origin": "http://localhost:3000"})
    assert "X-Request-ID" in response.headers.get("access-control-expose-headers", "")


def test_an_oversized_body_is_rejected(settings: Settings) -> None:
    settings.security.max_request_bytes = 100
    app: FastAPI = create_app(settings)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/meta", content=b"x" * 500)

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["max_bytes"] == 100


def test_a_body_within_the_limit_is_not_rejected_by_the_size_middleware(client: TestClient) -> None:
    # 405 (no POST route) proves the request passed the size gate and reached routing.
    response = client.post("/api/v1/meta", content=b"x" * 10)
    assert response.status_code == 405
