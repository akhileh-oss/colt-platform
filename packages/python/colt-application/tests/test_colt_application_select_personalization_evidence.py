"""`SelectPersonalizationEvidence` (CLAUDE.md §12.8, Milestone 15)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.errors import MessageValidationError
from colt_application.use_cases.select_personalization_evidence import (
    SelectPersonalizationEvidence,
)
from colt_domain import Evidence

NOW = datetime.now(UTC)


class FakeEvidenceRepository:
    def __init__(self, evidence: list[Evidence]) -> None:
        self._by_id = {e.id: e for e in evidence}

    async def add(self, **kwargs: object) -> Evidence:
        raise NotImplementedError

    async def get(self, evidence_id: UUID) -> Evidence | None:
        return self._by_id.get(evidence_id)

    async def list_by_entity(self, entity_type: str, entity_id: UUID) -> list[Evidence]:
        raise NotImplementedError


def _evidence() -> Evidence:
    return Evidence(
        id=uuid4(),
        organization_id=uuid4(),
        entity_type="Company",
        entity_id=uuid4(),
        claim="They raised a $20M Series B.",
        source_url="https://example.com/news",
        observed_at=NOW,
        created_at=NOW,
    )


@pytest.mark.asyncio
async def test_resolves_every_real_evidence_id() -> None:
    evidence = [_evidence(), _evidence()]
    select = SelectPersonalizationEvidence(FakeEvidenceRepository(evidence))

    result = await select([e.id for e in evidence])

    assert {e.id for e in result} == {e.id for e in evidence}


@pytest.mark.asyncio
async def test_rejects_an_empty_selection() -> None:
    select = SelectPersonalizationEvidence(FakeEvidenceRepository([]))

    with pytest.raises(MessageValidationError):
        await select([])


@pytest.mark.asyncio
async def test_rejects_an_evidence_id_that_does_not_exist_in_this_organization() -> None:
    evidence = _evidence()
    select = SelectPersonalizationEvidence(FakeEvidenceRepository([evidence]))

    with pytest.raises(MessageValidationError) as exc_info:
        await select([evidence.id, uuid4()])

    assert len(exc_info.value.issues) == 1
