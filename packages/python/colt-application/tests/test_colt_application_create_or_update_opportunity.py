"""`CreateOrUpdateOpportunity` (CLAUDE.md §10.14, §11.3, §12.11, Milestone 21)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from colt_application.use_cases.create_or_update_opportunity import CreateOrUpdateOpportunity
from colt_domain import Opportunity, PipelineStage

NOW = datetime.now(UTC)


class FakeOpportunityRepository:
    def __init__(self) -> None:
        self._by_id: dict[UUID, Opportunity] = {}
        self.added: list[Opportunity] = []

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
        opportunity = Opportunity(
            id=uuid4(),
            organization_id=uuid4(),
            company_id=company_id,
            primary_person_id=primary_person_id,
            lead_id=lead_id,
            pipeline_stage=pipeline_stage,
            estimated_value=estimated_value,
            currency=currency,
            probability=probability,
            owner_id=owner_id,
            source=source,
            is_estimated_value=is_estimated_value,
            created_at=NOW,
            updated_at=NOW,
        )
        self._by_id[opportunity.id] = opportunity
        self.added.append(opportunity)
        return opportunity

    async def get(self, opportunity_id: UUID) -> Opportunity | None:
        return self._by_id.get(opportunity_id)

    async def get_open_by_company(self, company_id: UUID) -> Opportunity | None:
        open_stages = frozenset(PipelineStage) - {PipelineStage.WON, PipelineStage.LOST}
        for opportunity in self._by_id.values():
            if opportunity.company_id == company_id and opportunity.pipeline_stage in open_stages:
                return opportunity
        return None

    async def list_all(self) -> list[Opportunity]:
        return list(self._by_id.values())

    async def update_stage(
        self, opportunity_id: UUID, stage: PipelineStage, *, at: datetime
    ) -> Opportunity:
        updated = self._by_id[opportunity_id].with_stage(stage, at=at)
        self._by_id[opportunity_id] = updated
        return updated

    async def assign_owner(
        self, opportunity_id: UUID, owner_id: UUID, *, at: datetime
    ) -> Opportunity:
        updated = self._by_id[opportunity_id].with_owner(owner_id, at=at)
        self._by_id[opportunity_id] = updated
        return updated

    async def update_value(
        self,
        opportunity_id: UUID,
        *,
        estimated_value: float,
        currency: str,
        is_estimate: bool,
        at: datetime,
    ) -> Opportunity:
        updated = self._by_id[opportunity_id].with_value(
            estimated_value=estimated_value, currency=currency, is_estimate=is_estimate, at=at
        )
        self._by_id[opportunity_id] = updated
        return updated


async def test_a_first_call_for_a_company_creates_a_new_opportunity() -> None:
    repo = FakeOpportunityRepository()
    create_or_update = CreateOrUpdateOpportunity(repo)
    company_id = uuid4()

    result = await create_or_update(company_id=company_id, source="conversation", now=NOW)

    assert result.was_created is True
    assert result.opportunity.company_id == company_id
    assert result.opportunity.pipeline_stage == PipelineStage.QUALIFIED
    assert len(repo.added) == 1


async def test_a_second_call_for_the_same_open_company_does_not_create_a_duplicate() -> None:
    repo = FakeOpportunityRepository()
    create_or_update = CreateOrUpdateOpportunity(repo)
    company_id = uuid4()

    first = await create_or_update(company_id=company_id, source="conversation", now=NOW)
    second = await create_or_update(company_id=company_id, source="conversation", now=NOW)

    assert second.was_created is False
    assert second.opportunity.id == first.opportunity.id
    assert len(repo.added) == 1


async def test_a_call_against_a_closed_opportunitys_company_creates_a_new_one() -> None:
    repo = FakeOpportunityRepository()
    create_or_update = CreateOrUpdateOpportunity(repo)
    company_id = uuid4()

    first = await create_or_update(company_id=company_id, source="conversation", now=NOW)
    await repo.update_stage(first.opportunity.id, PipelineStage.WON, at=NOW)

    second = await create_or_update(company_id=company_id, source="conversation", now=NOW)

    assert second.was_created is True
    assert second.opportunity.id != first.opportunity.id
    assert len(repo.added) == 2


async def test_a_value_offered_to_an_existing_valueless_opportunity_updates_it_in_place() -> None:
    repo = FakeOpportunityRepository()
    create_or_update = CreateOrUpdateOpportunity(repo)
    company_id = uuid4()

    first = await create_or_update(company_id=company_id, source="conversation", now=NOW)
    assert first.opportunity.estimated_value is None

    second = await create_or_update(
        company_id=company_id,
        source="conversation",
        estimated_value=25000.0,
        currency="USD",
        is_estimate=True,
        now=NOW,
    )

    assert second.was_created is False
    assert second.opportunity.id == first.opportunity.id
    assert second.opportunity.estimated_value == 25000.0
    assert second.opportunity.is_estimated_value is True
    assert len(repo.added) == 1


async def test_a_value_offered_when_one_already_exists_does_not_overwrite_it() -> None:
    repo = FakeOpportunityRepository()
    create_or_update = CreateOrUpdateOpportunity(repo)
    company_id = uuid4()

    await create_or_update(
        company_id=company_id,
        source="conversation",
        estimated_value=10000.0,
        currency="USD",
        is_estimate=False,
        now=NOW,
    )
    second = await create_or_update(
        company_id=company_id,
        source="conversation",
        estimated_value=99999.0,
        currency="USD",
        is_estimate=True,
        now=NOW,
    )

    assert second.opportunity.estimated_value == 10000.0
    assert second.opportunity.is_estimated_value is False
