"""Route-level tests for the campaigns router (CLAUDE.md §68, Milestone 14).

Hits real Postgres through `DbSessionDep` (the same default `DATABASE_URL` `colt_config`
ships, matching `tests/integration/`'s `APP_URL`), while faking only identity verification via
`app.dependency_overrides[principal_provider]` — the same pattern `test_colt_api_auth.py`
already established for `/api/v1/me`. A real `Organization` row must exist first:
`campaigns.organization_id` has a real foreign key to `organizations.id`, so the override alone
(without a seeded row) would fail every write with an `IntegrityError`, not a clean 4xx.

`tests/integration/test_campaign_engine.py` separately proves the full lifecycle's literal
acceptance criterion against real Postgres, bypassing HTTP entirely; this file instead proves
the router's own wiring — permission gating per CLAUDE.md §26, and the error-taxonomy mapping
(`NotFoundError` → 404, `CampaignValidationError` → 422, `InvalidCampaignTransitionError` → 409).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from colt_api.dependencies import principal_provider
from colt_application import OrganizationContext
from colt_domain import Organization, Role, User

APP_URL = "postgresql+asyncpg://colt_app:colt_app@localhost:5432/colt"
#: `colt_app` is the restricted role every request actually uses, and deliberately lacks
#: TRUNCATE privilege (ADR-0005) — cleanup needs the migration role instead.
SUPERUSER_URL = "postgresql+asyncpg://colt:colt@localhost:5432/colt"
NOW = datetime.now(UTC)

_FULLY_CONFIGURED = {
    "name": "Q4 outbound",
    "icp_definition": {"industry": "SaaS"},
    "channels": ["email"],
    "schedule": {"timezone": "UTC"},
    "limits": {"max_sends_per_day": 50},
}


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(APP_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()
    superuser_engine = create_async_engine(SUPERUSER_URL, pool_pre_ping=True)
    async with superuser_engine.begin() as conn:
        await conn.execute(text("TRUNCATE organizations CASCADE"))
    await superuser_engine.dispose()


def _context(org_id: UUID, *, role: Role) -> OrganizationContext:
    org = Organization(id=org_id, name="Acme", slug="acme", created_at=NOW, updated_at=NOW)
    user = User(
        id=uuid4(),
        organization_id=org_id,
        external_auth_id="kc-sub-1",
        email="a@acme.io",
        name="Ada",
        role=role,
        created_at=NOW,
        updated_at=NOW,
    )
    return OrganizationContext(organization=org, user=user)


@pytest_asyncio.fixture
async def org_id(db_engine: AsyncEngine) -> UUID:
    """Seed a real `Organization` row — `campaigns.organization_id` has a real FK to it."""
    new_id = uuid4()
    async with db_engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO organizations (id, name, slug) VALUES (:id, 'Acme', :slug)"),
            {"id": new_id, "slug": f"acme-{str(uuid4())[:8]}"},
        )
    return new_id


def _as(app: FastAPI, org_id: UUID, *, role: Role) -> None:
    app.dependency_overrides[principal_provider] = lambda: _context(org_id, role=role)


def test_create_campaign_is_denied_to_a_role_without_campaign_write(
    app: FastAPI, org_id: UUID
) -> None:
    _as(app, org_id, role=Role.VIEWER)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/campaigns",
            json=_FULLY_CONFIGURED,
            headers={"Authorization": "Bearer whatever"},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "POLICY_DENIED"


def test_create_campaign_succeeds_and_starts_in_draft(app: FastAPI, org_id: UUID) -> None:
    _as(app, org_id, role=Role.MANAGER)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/campaigns",
            json=_FULLY_CONFIGURED,
            headers={"Authorization": "Bearer whatever"},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["name"] == "Q4 outbound"
    assert body["organization_id"] == str(org_id)


def test_get_campaign_404s_for_an_unknown_id(app: FastAPI, org_id: UUID) -> None:
    _as(app, org_id, role=Role.VIEWER)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            f"/api/v1/campaigns/{uuid4()}", headers={"Authorization": "Bearer whatever"}
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_list_then_get_round_trips_a_created_campaign(app: FastAPI, org_id: UUID) -> None:
    _as(app, org_id, role=Role.MANAGER)
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer whatever"}
        created = client.post("/api/v1/campaigns", json=_FULLY_CONFIGURED, headers=headers)
        campaign_id = created.json()["id"]

        listed = client.get("/api/v1/campaigns", headers=headers)
        assert listed.status_code == 200
        assert any(c["id"] == campaign_id for c in listed.json()["campaigns"])

        fetched = client.get(f"/api/v1/campaigns/{campaign_id}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["id"] == campaign_id


def test_validate_with_a_missing_required_field_returns_422_with_every_issue(
    app: FastAPI, org_id: UUID
) -> None:
    _as(app, org_id, role=Role.MARKETING)
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer whatever"}
        created = client.post(
            "/api/v1/campaigns", json={"name": "Incomplete draft"}, headers=headers
        )
        campaign_id = created.json()["id"]

        response = client.post(f"/api/v1/campaigns/{campaign_id}/validate", headers=headers)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert len(body["error"]["details"]["issues"]) == 4


def test_validate_requires_campaign_launch_not_just_write(app: FastAPI, org_id: UUID) -> None:
    _as(app, org_id, role=Role.MANAGER)
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer whatever"}
        created = client.post("/api/v1/campaigns", json=_FULLY_CONFIGURED, headers=headers)
        campaign_id = created.json()["id"]

    _as(app, org_id, role=Role.SALES)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"/api/v1/campaigns/{campaign_id}/validate",
            headers={"Authorization": "Bearer whatever"},
        )
    assert response.status_code == 403


def test_the_full_lifecycle_validate_pause_resume_over_http(app: FastAPI, org_id: UUID) -> None:
    _as(app, org_id, role=Role.MANAGER)
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer whatever"}
        created = client.post("/api/v1/campaigns", json=_FULLY_CONFIGURED, headers=headers)
        campaign_id = created.json()["id"]

        validated = client.post(f"/api/v1/campaigns/{campaign_id}/validate", headers=headers)
        assert validated.status_code == 200
        assert validated.json()["status"] == "ACTIVE"

        paused = client.post(f"/api/v1/campaigns/{campaign_id}/pause", headers=headers)
        assert paused.status_code == 200
        assert paused.json()["status"] == "PAUSED"

        # Pausing an already-paused campaign is a conflict, not a validation error.
        conflict = client.post(f"/api/v1/campaigns/{campaign_id}/pause", headers=headers)
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "CONFLICT"

        resumed = client.post(f"/api/v1/campaigns/{campaign_id}/resume", headers=headers)
        assert resumed.status_code == 200
        assert resumed.json()["status"] == "ACTIVE"


def test_sequence_steps_can_be_added_and_are_listed_in_order(app: FastAPI, org_id: UUID) -> None:
    _as(app, org_id, role=Role.MANAGER)
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer whatever"}
        created = client.post("/api/v1/campaigns", json=_FULLY_CONFIGURED, headers=headers)
        campaign_id = created.json()["id"]

        second = client.post(
            f"/api/v1/campaigns/{campaign_id}/sequence-steps",
            json={
                "step_order": 1,
                "channel": "linkedin",
                "message_strategy": "Follow-up",
                "delay_after_previous": 2880,
            },
            headers=headers,
        )
        assert second.status_code == 201
        assert second.json()["campaign_id"] == campaign_id

        first = client.post(
            f"/api/v1/campaigns/{campaign_id}/sequence-steps",
            json={"step_order": 0, "channel": "email", "message_strategy": "Opener"},
            headers=headers,
        )
        assert first.status_code == 201

        listed = client.get(f"/api/v1/campaigns/{campaign_id}/sequence-steps", headers=headers)

    assert listed.status_code == 200
    steps = listed.json()["sequence_steps"]
    assert [s["step_order"] for s in steps] == [0, 1]
    assert [s["channel"] for s in steps] == ["email", "linkedin"]


def test_adding_a_sequence_step_requires_campaign_write_not_just_read(
    app: FastAPI, org_id: UUID
) -> None:
    _as(app, org_id, role=Role.MANAGER)
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer whatever"}
        created = client.post("/api/v1/campaigns", json=_FULLY_CONFIGURED, headers=headers)
        campaign_id = created.json()["id"]

    _as(app, org_id, role=Role.SALES)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"/api/v1/campaigns/{campaign_id}/sequence-steps",
            json={"step_order": 0, "channel": "email", "message_strategy": "Opener"},
            headers={"Authorization": "Bearer whatever"},
        )
    assert response.status_code == 403


def test_listing_sequence_steps_404s_for_an_unknown_campaign(app: FastAPI, org_id: UUID) -> None:
    _as(app, org_id, role=Role.VIEWER)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            f"/api/v1/campaigns/{uuid4()}/sequence-steps",
            headers={"Authorization": "Bearer whatever"},
        )
    assert response.status_code == 404


def test_listing_messages_returns_an_empty_list_for_a_campaign_with_no_messages_yet(
    app: FastAPI, org_id: UUID
) -> None:
    _as(app, org_id, role=Role.MANAGER)
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer whatever"}
        created = client.post("/api/v1/campaigns", json=_FULLY_CONFIGURED, headers=headers)
        campaign_id = created.json()["id"]

        response = client.get(f"/api/v1/campaigns/{campaign_id}/messages", headers=headers)

    assert response.status_code == 200
    assert response.json()["messages"] == []


def test_listing_messages_requires_message_approve_permission(app: FastAPI, org_id: UUID) -> None:
    _as(app, org_id, role=Role.MANAGER)
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer whatever"}
        created = client.post("/api/v1/campaigns", json=_FULLY_CONFIGURED, headers=headers)
        campaign_id = created.json()["id"]

    _as(app, org_id, role=Role.VIEWER)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            f"/api/v1/campaigns/{campaign_id}/messages",
            headers={"Authorization": "Bearer whatever"},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "POLICY_DENIED"


def test_listing_messages_404s_for_an_unknown_campaign(app: FastAPI, org_id: UUID) -> None:
    _as(app, org_id, role=Role.MANAGER)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            f"/api/v1/campaigns/{uuid4()}/messages",
            headers={"Authorization": "Bearer whatever"},
        )
    assert response.status_code == 404
