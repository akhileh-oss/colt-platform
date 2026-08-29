"""Versioned API surface and the generated OpenAPI contract (CLAUDE.md §25)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from colt_api import __version__
from colt_api.app import create_app
from colt_api.routers.v1.router import API_V1_PREFIX
from colt_config import Environment, Settings


def test_api_v1_is_mounted_and_serves_meta(client: TestClient) -> None:
    response = client.get(f"{API_V1_PREFIX}/meta")
    assert response.status_code == 200
    assert response.json() == {
        "name": "colt",
        "version": __version__,
        "environment": "local",
        "api_version": "v1",
    }


def test_openapi_is_generated(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "Colt API"


def test_openapi_documents_the_versioned_and_probe_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert f"{API_V1_PREFIX}/meta" in paths
    assert "/live" in paths and "/ready" in paths


def test_openapi_publishes_the_error_envelope(client: TestClient) -> None:
    """Clients generate against this contract, so the error shape must be in it (§25.3, §44)."""
    schema = client.get("/openapi.json").json()
    assert "ErrorResponse" in schema["components"]["schemas"]
    error_detail = schema["components"]["schemas"]["ErrorDetail"]["properties"]
    assert {"code", "message", "request_id"} <= set(error_detail)


def test_interactive_docs_are_served_outside_production(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200


def test_interactive_docs_are_disabled_in_production(settings: Settings) -> None:
    """They widen the surface for no operator benefit once deployed."""
    settings.app.env = Environment.PRODUCTION
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        # The schema itself stays available for client generation.
        assert client.get("/openapi.json").status_code == 200
