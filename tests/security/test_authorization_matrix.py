"""Authorization (CLAUDE.md §26, §40, Milestone 24's "authorization tests" Build item) —
`apps/api/tests/test_colt_api_auth.py` already proves `require_permission`'s own wiring with one
example (a `VIEWER` denied `LEAD_WRITE`); this file is the full matrix: every `(Role,
Permission)` pair in `colt_domain.roles.DEFAULT_ROLE_PERMISSIONS`, asserting a role with the
permission is let through and a role without it gets a real 403 — the literal contract
`colt_domain.roles.DEFAULT_ROLE_PERMISSIONS` claims to be, exercised through the real FastAPI
dependency chain (`require_permission`), not just read back from the table that defines it.

Self-contained rather than reusing `apps/api/tests/conftest.py`'s fixtures: `tests/security/`
sits outside that suite's own fixture-resolution path, and a dedicated security-suite test
should not depend on another suite's test infrastructure to mean what it says.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from colt_api.app import create_app
from colt_api.dependencies import principal_provider, require_permission
from colt_api.readiness import readiness_registry
from colt_application import OrganizationContext
from colt_config import Settings
from colt_domain import DEFAULT_ROLE_PERMISSIONS, Organization, Permission, Role, User

pytestmark = pytest.mark.security

NOW = datetime.now(UTC)

_ALL_PAIRS = [(role, permission) for role in Role for permission in Permission]


def _context(role: Role) -> OrganizationContext:
    org = Organization(id=uuid4(), name="Acme", slug="acme", created_at=NOW, updated_at=NOW)
    user = User(
        id=uuid4(),
        organization_id=org.id,
        external_auth_id=f"kc-sub-{uuid4()}",
        email="a@acme.io",
        name="Ada",
        role=role,
        created_at=NOW,
        updated_at=NOW,
    )
    return OrganizationContext(organization=org, user=user)


@pytest.mark.parametrize(("role", "permission"), _ALL_PAIRS)
def test_role_permission_matrix_matches_the_declared_table(
    role: Role, permission: Permission
) -> None:
    app: FastAPI = create_app(Settings())
    readiness_registry.clear()
    context = _context(role)
    app.dependency_overrides[principal_provider] = lambda: context

    @app.get("/api/v1/_matrix_probe")
    async def _probe(
        principal: OrganizationContext = Depends(require_permission(permission)),  # noqa: B008
    ) -> dict[str, str]:
        return {"ok": "true"}

    expected_allowed = permission in DEFAULT_ROLE_PERMISSIONS[role]

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/_matrix_probe", headers={"Authorization": "Bearer whatever"})

    readiness_registry.clear()

    if expected_allowed:
        assert response.status_code == 200, (
            f"{role} has {permission} per DEFAULT_ROLE_PERMISSIONS but the route denied it"
        )
    else:
        assert response.status_code == 403, (
            f"{role} lacks {permission} per DEFAULT_ROLE_PERMISSIONS but the route allowed it"
        )
        assert response.json()["error"]["code"] == "POLICY_DENIED"
