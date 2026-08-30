"""The authenticated principal's identity (CLAUDE.md §27, §68 M04 acceptance).

Deliberately the first protected endpoint: it proves the whole auth chain end to end — bearer
token verified, organization context resolved, tenant scoping bound — without needing any
business domain to exist yet. Every future protected endpoint follows the same
`PrincipalDep` / `require_permission(...)` pattern this establishes.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from colt_api.dependencies import PrincipalDep
from colt_domain import OrganizationStatus, Role, UserStatus

router = APIRouter(prefix="/me", tags=["me"])


class OrganizationSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    status: OrganizationStatus


class UserSummary(BaseModel):
    id: UUID
    email: str
    name: str
    role: Role
    status: UserStatus


class MeResponse(BaseModel):
    organization: OrganizationSummary
    user: UserSummary


@router.get("", response_model=MeResponse, summary="The authenticated principal")
async def get_me(principal: PrincipalDep) -> MeResponse:
    """Return who the caller is and which organization they act within.

    Never returns `external_auth_id`: it is an internal identity-provider reference, not
    something a client needs.
    """
    return MeResponse(
        organization=OrganizationSummary(
            id=principal.organization.id,
            name=principal.organization.name,
            slug=principal.organization.slug,
            status=principal.organization.status,
        ),
        user=UserSummary(
            id=principal.user.id,
            email=principal.user.email,
            name=principal.user.name,
            role=principal.user.role,
            status=principal.user.status,
        ),
    )
