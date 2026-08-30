"""Auth dependency wiring, with fakes (CLAUDE.md §26, §27, §68 M04).

Fast and hermetic: JWT verification and organization-context resolution are overridden via
FastAPI's `dependency_overrides`, so these tests prove the *wiring* — which error maps to which
status, that a route needing a permission actually checks it — without needing Keycloak or
Postgres. `tests/integration/test_auth_end_to_end.py` separately proves the real components
(JWKS fetch, real token, real database) work together; that is where the `lru_cache`-on-an-
unhashable-Settings bug this milestone found actually surfaced, precisely because a fake
verifier here would never have constructed the real one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from colt_api.dependencies import principal_provider, require_permission
from colt_application import OrganizationContext
from colt_domain import Organization, Permission, Role, User

NOW = datetime.now(UTC)


def _context(role: Role = Role.OWNER) -> OrganizationContext:
    org = Organization(id=uuid4(), name="Acme", slug="acme", created_at=NOW, updated_at=NOW)
    user = User(
        id=uuid4(),
        organization_id=org.id,
        external_auth_id="kc-sub-1",
        email="a@acme.io",
        name="Ada",
        role=role,
        created_at=NOW,
        updated_at=NOW,
    )
    return OrganizationContext(organization=org, user=user)


def test_me_requires_a_token(client: TestClient) -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"


def test_me_rejects_a_malformed_authorization_header(client: TestClient) -> None:
    response = client.get("/api/v1/me", headers={"Authorization": "NotBearer xyz"})
    assert response.status_code == 401


def test_me_returns_the_resolved_principal(app: FastAPI) -> None:
    context = _context()
    app.dependency_overrides[principal_provider] = lambda: context

    with TestClient(app) as client:
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer whatever"})

    assert response.status_code == 200
    body = response.json()
    assert body["organization"]["id"] == str(context.organization.id)
    assert body["user"]["email"] == "a@acme.io"
    assert body["user"]["role"] == "OWNER"


def test_a_route_requiring_a_permission_the_principal_lacks_is_denied(app: FastAPI) -> None:
    context = _context(role=Role.VIEWER)
    app.dependency_overrides[principal_provider] = lambda: context

    @app.get("/api/v1/_needs_write")
    async def needs_write(
        principal: OrganizationContext = Depends(require_permission(Permission.LEAD_WRITE)),  # noqa: B008
    ) -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/_needs_write", headers={"Authorization": "Bearer whatever"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "POLICY_DENIED"


def test_a_route_requiring_a_permission_the_principal_has_succeeds(app: FastAPI) -> None:
    context = _context(role=Role.OWNER)
    app.dependency_overrides[principal_provider] = lambda: context

    @app.get("/api/v1/_needs_write_ok")
    async def needs_write_ok(
        principal: OrganizationContext = Depends(require_permission(Permission.LEAD_WRITE)),  # noqa: B008
    ) -> dict[str, str]:
        return {"organization": principal.organization.slug}

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/_needs_write_ok", headers={"Authorization": "Bearer whatever"}
        )

    assert response.status_code == 200
    assert response.json() == {"organization": "acme"}
