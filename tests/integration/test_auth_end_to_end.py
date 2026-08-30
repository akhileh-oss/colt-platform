"""The full auth chain against real Keycloak and real Postgres (CLAUDE.md §68 M04 acceptance).

Deliberately does not mock or override anything: this is the one test that would have caught
the `lru_cache`-on-an-unhashable-`Settings` bug this milestone found (fast tests in
`apps/api/tests/test_colt_api_auth.py` override `principal_provider` entirely, so they never
construct a real `JwtVerifier`). Requires local Keycloak with the `colt` realm imported
(Milestone 01) and the two organizations seeded (`make seed`).
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from colt_api.app import create_app
from colt_db.dev_seed import seed_dev_organizations_and_users
from colt_db.session import get_default_engine

KEYCLOAK_TOKEN_URL = "http://localhost:8081/realms/colt/protocol/openid-connect/token"  # noqa: S105 - a URL, not a credential


@pytest.fixture(autouse=True)
async def _seed_identities() -> None:
    """Re-seed Alice and Bob before every test in this file.

    `tests/integration/conftest.py`'s `_clean_tables` fixture truncates `users` and
    `organizations` after every test in this directory — needed for `test_tenant_isolation.py`'s
    self-seeding tests, but it means this file cannot rely on `make seed` having been run once
    out of band: whatever it inserted is gone after the first test. Seeding here instead makes
    this file correct regardless of execution order.
    """
    engine = get_default_engine()
    async with engine.begin() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)
        await seed_dev_organizations_and_users(session)


def _fetch_token(username: str, password: str) -> str:
    response = httpx.post(
        KEYCLOAK_TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": "colt-api",
            "client_secret": "colt-api-secret",
            "username": username,
            "password": password,
            "scope": "openid",
        },
        timeout=10,
    )
    response.raise_for_status()
    token: str = response.json()["access_token"]
    return token


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    with TestClient(create_app()) as client:
        yield client


def test_me_with_no_token_is_401(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/me")
    assert response.status_code == 401


def test_alice_resolves_to_acme_corp(api_client: TestClient) -> None:
    token = _fetch_token("alice", "alice-dev-password")
    response = api_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["organization"]["slug"] == "acme-corp"
    assert body["user"]["email"] == "alice@acme-corp.example"
    assert body["user"]["role"] == "OWNER"


def test_bob_resolves_to_a_different_organization_than_alice(api_client: TestClient) -> None:
    alice_token = _fetch_token("alice", "alice-dev-password")
    bob_token = _fetch_token("bob", "bob-dev-password")

    alice_org = api_client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {alice_token}"}
    ).json()["organization"]["slug"]
    bob_org = api_client.get("/api/v1/me", headers={"Authorization": f"Bearer {bob_token}"}).json()[
        "organization"
    ]["slug"]

    assert alice_org == "acme-corp"
    assert bob_org == "globex-inc"
    assert alice_org != bob_org


def test_a_tampered_token_is_rejected(api_client: TestClient) -> None:
    real_token = _fetch_token("alice", "alice-dev-password")
    tampered = real_token[:-4] + "aaaa"  # corrupt the signature

    response = api_client.get("/api/v1/me", headers={"Authorization": f"Bearer {tampered}"})

    assert response.status_code == 401


def test_readiness_reports_a_real_database_connection(api_client: TestClient) -> None:
    response = api_client.get("/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["database"] == {"ready": True, "detail": None}
