"""Resolve a verified identity to its organization and role (CLAUDE.md §27, ADR-0005).

The one place `organization_id` is allowed to come from anything other than an already-trusted
source: it looks a subject up by the identity provider's verified claim and returns what *our*
system of record says about them. Everything downstream receives an `OrganizationContext`, never
a client-supplied organization id.
"""

from __future__ import annotations

from dataclasses import dataclass

from colt_application.errors import OrganizationContextError
from colt_application.ports.organization_repository import OrganizationRepository
from colt_application.ports.user_repository import UserDirectory
from colt_domain import Organization, User


@dataclass(frozen=True, slots=True)
class OrganizationContext:
    """Everything downstream authorization and tenant scoping needs, resolved once per request."""

    organization: Organization
    user: User


class ResolveOrganizationContext:
    """Use case: verified external identity → organization context."""

    def __init__(
        self, user_directory: UserDirectory, organizations: OrganizationRepository
    ) -> None:
        self._user_directory = user_directory
        self._organizations = organizations

    async def __call__(self, external_auth_id: str) -> OrganizationContext:
        user = await self._user_directory.find_by_external_auth_id(external_auth_id)
        if user is None or not user.is_active:
            # Same error for "no such user" and "user exists but is suspended" — see
            # OrganizationContextError's docstring for why that is deliberate.
            raise OrganizationContextError("No active user found for this identity.")

        organization = await self._organizations.get(user.organization_id)
        if organization is None or not organization.is_active:
            raise OrganizationContextError(
                "The user's organization does not exist or is not active."
            )

        return OrganizationContext(organization=organization, user=user)
