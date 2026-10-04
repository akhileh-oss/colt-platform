"""`ListEvidenceForLead` (CLAUDE.md §12.8, Milestone 15)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError
from colt_application.use_cases.list_evidence_for_lead import ListEvidenceForLead
from colt_domain import Evidence, Lead

NOW = datetime.now(UTC)


class FakeLeadRepository:
    def __init__(self, lead: Lead | None) -> None:
        self.lead = lead

    async def get(self, lead_id: UUID) -> Lead | None:
        return self.lead if self.lead and lead_id == self.lead.id else None

    async def update_status(self, lead_id: UUID, status: object, *, at: datetime) -> Lead:
        raise NotImplementedError


class FakeEvidenceRepository:
    def __init__(self, evidence: list[Evidence]) -> None:
        self._evidence = evidence

    async def add(self, **kwargs: object) -> Evidence:
        raise NotImplementedError

    async def get(self, evidence_id: UUID) -> Evidence | None:
        raise NotImplementedError

    async def list_by_entity(self, entity_type: str, entity_id: UUID) -> list[Evidence]:
        return [
            e for e in self._evidence if e.entity_type == entity_type and e.entity_id == entity_id
        ]


def _evidence(entity_type: str, entity_id: UUID) -> Evidence:
    return Evidence(
        id=uuid4(),
        organization_id=uuid4(),
        entity_type=entity_type,
        entity_id=entity_id,
        claim="They raised a $20M Series B.",
        source_url="https://example.com/news",
        observed_at=NOW,
        created_at=NOW,
    )


def _lead(company_id: UUID, person_id: UUID) -> Lead:
    return Lead(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=company_id,
        person_id=person_id,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_returns_the_union_of_company_and_person_evidence() -> None:
    company_id, person_id = uuid4(), uuid4()
    lead = _lead(company_id, person_id)
    company_evidence = _evidence("Company", company_id)
    person_evidence = _evidence("Person", person_id)
    unrelated = _evidence("Company", uuid4())

    list_evidence = ListEvidenceForLead(
        FakeLeadRepository(lead),
        FakeEvidenceRepository([company_evidence, person_evidence, unrelated]),
    )

    result = await list_evidence(lead.id)

    assert {e.id for e in result} == {company_evidence.id, person_evidence.id}


@pytest.mark.asyncio
async def test_raises_not_found_for_a_lead_outside_this_organization() -> None:
    list_evidence = ListEvidenceForLead(FakeLeadRepository(None), FakeEvidenceRepository([]))

    with pytest.raises(NotFoundError):
        await list_evidence(uuid4())
