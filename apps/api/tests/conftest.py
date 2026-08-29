"""Shared fixtures for the API test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from colt_api.app import create_app
from colt_api.readiness import readiness_registry
from colt_config import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    """Declared defaults, independent of whatever the developer has in .env.

    ``env_file`` is a relative path, so running from an empty directory discovers none.
    """
    monkeypatch.chdir(tmp_path)
    return Settings()


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    readiness_registry.clear()
    yield create_app(settings)
    readiness_registry.clear()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # raise_server_exceptions=False so the 500 handler is exercised as a client would see it,
    # rather than the exception propagating into the test.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
