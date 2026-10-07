"""`TransitionOpportunityStage` (CLAUDE.md §11.3, Milestone 21)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.errors import InvalidOpportunityTransitionError, NotFoundError
from colt_application.use_cases.transition_opportunity_stage import TransitionOpportunityStage
from colt_domain import Opportunity, PipelineStage

NOW = datetime.now(UTC)


class FakeOpportunityRepository:
    def __init__(self, opportunity: Opportunity | None) -> None:
        self.opportunity = opportunity

    async def get(self, opportunity_id: UUID) -> Opportunity | None:
        return (
            self.opportunity if self.opportunity and opportunity_id == self.opportunity.id else None
        )

    async def update_stage(
        self, opportunity_id: UUID, stage: PipelineStage, *, at: datetime
    ) -> Opportunity:
        assert self.opportunity is not None
        self.opportunity = self.opportunity.with_stage(stage, at=at)
        return self.opportunity

    async def add(self, **kwargs: object) -> Opportunity:
        raise NotImplementedError

    async def get_open_by_company(self, company_id: UUID) -> Opportunity | None:
        raise NotImplementedError

    async def list_all(self) -> list[Opportunity]:
        raise NotImplementedError

    async def assign_owner(
        self, opportunity_id: UUID, owner_id: UUID, *, at: datetime
    ) -> Opportunity:
        raise NotImplementedError

    async def update_value(self, opportunity_id: UUID, **kwargs: object) -> Opportunity:
        raise NotImplementedError


def _opportunity(stage: PipelineStage = PipelineStage.QUALIFIED) -> Opportunity:
    return Opportunity(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        pipeline_stage=stage,
        created_at=NOW,
        updated_at=NOW,
    )


async def test_a_legal_transition_updates_the_stage() -> None:
    opportunity = _opportunity(PipelineStage.QUALIFIED)
    repo = FakeOpportunityRepository(opportunity)
    transition = TransitionOpportunityStage(repo)

    updated = await transition(opportunity.id, PipelineStage.DISCOVERY, now=NOW)

    assert updated.pipeline_stage == PipelineStage.DISCOVERY


async def test_an_illegal_transition_raises_and_does_not_change_the_stage() -> None:
    opportunity = _opportunity(PipelineStage.QUALIFIED)
    repo = FakeOpportunityRepository(opportunity)
    transition = TransitionOpportunityStage(repo)

    with pytest.raises(InvalidOpportunityTransitionError):
        await transition(opportunity.id, PipelineStage.WON, now=NOW)

    assert repo.opportunity is not None
    assert repo.opportunity.pipeline_stage == PipelineStage.QUALIFIED


async def test_a_terminal_opportunity_can_never_transition_again() -> None:
    opportunity = _opportunity(PipelineStage.WON)
    repo = FakeOpportunityRepository(opportunity)
    transition = TransitionOpportunityStage(repo)

    with pytest.raises(InvalidOpportunityTransitionError):
        await transition(opportunity.id, PipelineStage.NEGOTIATION, now=NOW)


async def test_raises_not_found_for_an_unknown_opportunity() -> None:
    repo = FakeOpportunityRepository(None)
    transition = TransitionOpportunityStage(repo)

    with pytest.raises(NotFoundError):
        await transition(uuid4(), PipelineStage.DISCOVERY, now=NOW)
