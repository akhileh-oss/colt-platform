"""ResolveOrganizationContext (CLAUDE.md §27, ADR-0005).

Ports are faked in-memory here — no database. `colt-db`'s integration tests separately prove
the SQLAlchemy implementations satisfy these same ports against real Postgres and real RLS.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.errors import OrganizationContextError
from colt_application.use_cases.resolve_organization_context import ResolveOrganizationContext
from colt_domain import Organization, OrganizationStatus, Role, User, UserStatus

NOW = datetime.now(UTC)


class FakeUserDirectory:
    def __init__(self, users: list[User]) -> None:
        self._by_external_id = {u.external_auth_id: u for u in users}

    async def find_by_external_auth_id(self, external_auth_id: str) -> User | None:
        return self._by_external_id.get(external_auth_id)


class FakeOrganizationRepository:
    def __init__(self, organizations: list[Organization]) -> None:
        self._by_id = {o.id: o for o in organizations}

    async def get(self, organization_id: UUID) -> Organization | None:
        return self._by_id.get(organization_id)

    async def get_by_slug(self, slug: str) -> Organization | None:
        raise NotImplementedError


def _organization(*, status: OrganizationStatus = OrganizationStatus.ACTIVE) -> Organization:
    return Organization(
        id=uuid4(), name="Acme", slug="acme", status=status, created_at=NOW, updated_at=NOW
    )


def _user(
    organization_id: UUID,
    *,
    external_auth_id: str = "kc-sub-1",
    role: Role = Role.SALES,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    return User(
        id=uuid4(),
        organization_id=organization_id,
        external_auth_id=external_auth_id,
        email="a@acme.io",
        name="Ada",
        role=role,
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_resolves_an_active_user_to_their_organization() -> None:
    org = _organization()
    user = _user(org.id, external_auth_id="kc-sub-1")
    resolve = ResolveOrganizationContext(
        FakeUserDirectory([user]), FakeOrganizationRepository([org])
    )

    context = await resolve("kc-sub-1")

    assert context.user.id == user.id
    assert context.organization.id == org.id


@pytest.mark.asyncio
async def test_unknown_identity_is_rejected() -> None:
    resolve = ResolveOrganizationContext(FakeUserDirectory([]), FakeOrganizationRepository([]))
    with pytest.raises(OrganizationContextError):
        await resolve("no-such-subject")


@pytest.mark.asyncio
async def test_suspended_user_is_rejected() -> None:
    org = _organization()
    user = _user(org.id, external_auth_id="kc-sub-1", status=UserStatus.SUSPENDED)
    resolve = ResolveOrganizationContext(
        FakeUserDirectory([user]), FakeOrganizationRepository([org])
    )

    with pytest.raises(OrganizationContextError):
        await resolve("kc-sub-1")


@pytest.mark.asyncio
async def test_archived_organization_is_rejected_even_for_an_active_user() -> None:
    org = _organization(status=OrganizationStatus.ARCHIVED)
    user = _user(org.id, external_auth_id="kc-sub-1")
    resolve = ResolveOrganizationContext(
        FakeUserDirectory([user]), FakeOrganizationRepository([org])
    )

    with pytest.raises(OrganizationContextError):
        await resolve("kc-sub-1")


@pytest.mark.asyncio
async def test_unknown_identity_and_suspended_user_fail_identically() -> None:
    """The two cases must be indistinguishable to a caller — see OrganizationContextError's
    docstring: a different error per case would let an attacker enumerate valid identities."""
    org = _organization()
    suspended = _user(org.id, external_auth_id="kc-sub-1", status=UserStatus.SUSPENDED)
    resolve = ResolveOrganizationContext(
        FakeUserDirectory([suspended]), FakeOrganizationRepository([org])
    )

    unknown_error = None
    suspended_error = None
    try:
        await resolve("no-such-subject")
    except OrganizationContextError as exc:
        unknown_error = str(exc)
    try:
        await resolve("kc-sub-1")
    except OrganizationContextError as exc:
        suspended_error = str(exc)

    assert unknown_error == suspended_error
