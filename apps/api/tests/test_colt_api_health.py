"""Liveness and readiness (CLAUDE.md §57)."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from colt_api.readiness import readiness_registry


def test_liveness_reports_alive(client: TestClient) -> None:
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_is_ready_with_no_registered_dependencies(client: TestClient) -> None:
    """At Milestone 02 the API has no required dependencies; the registry fills in later."""
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {}}


def test_readiness_reports_503_when_a_dependency_is_unhealthy(app: FastAPI) -> None:
    async def failing() -> str:
        return "connection refused"

    readiness_registry.register("database", failing)
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == {"ready": False, "detail": "connection refused"}


def test_readiness_survives_a_check_that_raises(app: FastAPI) -> None:
    async def exploding() -> str | None:
        raise RuntimeError("pool exhausted")

    readiness_registry.register("database", exploding)
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert "pool exhausted" in response.json()["checks"]["database"]["detail"]


def test_readiness_fails_a_hanging_check_rather_than_hanging(app: FastAPI) -> None:
    """A stuck dependency must not stall the probe itself."""

    async def hanging() -> str | None:
        await asyncio.sleep(60)
        return None

    readiness_registry.register("slow", hanging)
    import colt_api.readiness as readiness_module

    original = readiness_module._CHECK_TIMEOUT_SECONDS
    readiness_module._CHECK_TIMEOUT_SECONDS = 0.05
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        readiness_module._CHECK_TIMEOUT_SECONDS = original

    assert response.status_code == 503
    assert response.json()["checks"]["slow"]["detail"] == "timed out"


def test_liveness_stays_up_when_a_dependency_is_down(app: FastAPI) -> None:
    """Liveness must not depend on external services, or a blip causes restart storms (§57)."""

    async def failing() -> str:
        return "down"

    readiness_registry.register("database", failing)
    with TestClient(app) as client:
        assert client.get("/live").status_code == 200
        assert client.get("/ready").status_code == 503
