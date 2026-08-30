"""User entity invariants and permission checks (CLAUDE.md §10.2, §26.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from colt_domain import Permission, Role, User, UserStatus

NOW = datetime.now(UTC)


def _make(
    *,
    email: str = "ada@acme-corp.io",
    external_auth_id: str = "kc-sub-123",
    role: Role = Role.SALES,
) -> User:
    return User(
        id=uuid4(),
        organization_id=uuid4(),
        external_auth_id=external_auth_id,
        email=email,
        name="Ada Lovelace",
        role=role,
        created_at=NOW,
        updated_at=NOW,
    )


def test_defaults_to_active() -> None:
    assert _make().status is UserStatus.ACTIVE
    assert _make().is_active


def test_invalid_email_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _make(email="not-an-email")


def test_blank_external_auth_id_is_rejected() -> None:
    with pytest.raises(ValidationError, match="external_auth_id"):
        _make(external_auth_id="   ")


def test_owner_has_every_permission() -> None:
    owner = _make(role=Role.OWNER)
    for permission in Permission:
        assert owner.has_permission(permission), f"OWNER should have {permission}"


def test_viewer_cannot_write() -> None:
    viewer = _make(role=Role.VIEWER)
    assert viewer.has_permission(Permission.COMPANY_READ)
    assert not viewer.has_permission(Permission.COMPANY_WRITE)
    assert not viewer.has_permission(Permission.SETTINGS_ADMIN)


def test_service_agent_has_no_standing_permissions() -> None:
    """CLAUDE.md §26.3: a service identity is granted exactly what its workflow needs."""
    service = _make(role=Role.SERVICE_AGENT)
    assert service.is_service_identity
    for permission in Permission:
        assert not service.has_permission(permission)


def test_entity_is_frozen() -> None:
    user = _make()
    with pytest.raises(ValidationError):
        user.role = Role.OWNER


def test_with_role_returns_a_new_instance() -> None:
    user = _make(role=Role.VIEWER)
    later = datetime.now(UTC)
    promoted = user.with_role(Role.ADMIN, at=later)

    assert user.role is Role.VIEWER, "original must be unchanged"
    assert promoted.role is Role.ADMIN
    assert promoted.updated_at == later
