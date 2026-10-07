"""`AssignOpportunityOwner` (CLAUDE.md §10.14, Milestone 21)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError
from colt_application.use_cases.assign_opportunity_owner import AssignOpportunityOwner
from colt_domain import Opportunity, PipelineStage, Role, User, UserStatus

NOW = datetime.now(UTC)


class FakeOpportunityRepository:
    def __init__(self, opportunity: Opportunity | None) -> None:
        self.opportunity = opportunity

    async def get(self, opportunity_id: UUID) -> Opportunity | None:
        return (
            self.opportunity if self.opportunity and opportunity_id == self.opportunity.id else None
        )

    async def assign_owner(
        self, opportunity_id: UUID, owner_id: UUID, *, at: datetime
    ) -> Opportunity:
        assert self.opportunity is not None
        self.opportunity = self.opportunity.with_owner(owner_id, at=at)
        return self.opportunity

    async def add(
        self,
        *,
        company_id: UUID,
        primary_person_id: UUID | None = None,
        lead_id: UUID | None = None,
        pipeline_stage: PipelineStage = PipelineStage.QUALIFIED,
        estimated_value: float | None = None,
        currency: str | None = None,
        probability: float | None = None,
        owner_id: UUID | None = None,
        source: str | None = None,
        is_estimated_value: bool = False,
    ) -> Opportunity:
        raise NotImplementedError

    async def get_open_by_company(self, company_id: UUID) -> Opportunity | None:
        raise NotImplementedError

    async def list_all(self) -> list[Opportunity]:
        raise NotImplementedError

    async def update_stage(
        self, opportunity_id: UUID, stage: PipelineStage, *, at: datetime
    ) -> Opportunity:
        raise NotImplementedError

    async def update_value(
        self,
        opportunity_id: UUID,
        *,
        estimated_value: float,
        currency: str,
        is_estimate: bool,
        at: datetime,
    ) -> Opportunity:
        raise NotImplementedError


class FakeUserRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get(self, user_id: UUID) -> User | None:
        return self.user if self.user and user_id == self.user.id else None

    async def list_active(self) -> list[User]:
        raise NotImplementedError


def _opportunity() -> Opportunity:
    return Opportunity(
        id=uuid4(), organization_id=uuid4(), company_id=uuid4(), created_at=NOW, updated_at=NOW
    )


def _user() -> User:
    return User(
        id=uuid4(),
        organization_id=uuid4(),
        external_auth_id="auth0|abc",
        email="rep@a.example",
        name="Rep",
        role=Role.SALES,
        status=UserStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )


async def test_assigns_a_real_users_id_to_the_opportunity() -> None:
    opportunity = _opportunity()
    owner = _user()
    assign = AssignOpportunityOwner(
        FakeOpportunityRepository(opportunity), FakeUserRepository(owner)
    )

    updated = await assign(opportunity.id, owner.id, now=NOW)

    assert updated.owner_id == owner.id


async def test_raises_not_found_for_an_unknown_opportunity() -> None:
    assign = AssignOpportunityOwner(FakeOpportunityRepository(None), FakeUserRepository(_user()))

    with pytest.raises(NotFoundError):
        await assign(uuid4(), uuid4(), now=NOW)


async def test_raises_not_found_for_an_unknown_or_cross_tenant_owner() -> None:
    opportunity = _opportunity()
    assign = AssignOpportunityOwner(
        FakeOpportunityRepository(opportunity), FakeUserRepository(None)
    )

    with pytest.raises(NotFoundError):
        await assign(opportunity.id, uuid4(), now=NOW)
