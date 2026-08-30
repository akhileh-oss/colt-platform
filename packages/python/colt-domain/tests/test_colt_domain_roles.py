"""The role → permission matrix (CLAUDE.md §26.2)."""

from __future__ import annotations

import pytest

from colt_domain import (
    DEFAULT_ROLE_PERMISSIONS,
    Permission,
    Role,
    permissions_for,
    role_has_permission,
)


def test_every_role_has_a_permission_mapping() -> None:
    """A missing entry would KeyError at request time rather than fail a test."""
    assert set(DEFAULT_ROLE_PERMISSIONS) == set(Role)


def test_owner_permissions_are_a_superset_of_every_other_role() -> None:
    owner_permissions = permissions_for(Role.OWNER)
    for role in Role:
        if role is Role.OWNER:
            continue
        assert permissions_for(role) <= owner_permissions, f"{role} exceeds OWNER's permissions"


@pytest.mark.parametrize("role", list(Role))
def test_role_has_permission_matches_the_matrix(role: Role) -> None:
    for permission in Permission:
        expected = permission in DEFAULT_ROLE_PERMISSIONS[role]
        assert role_has_permission(role, permission) is expected
