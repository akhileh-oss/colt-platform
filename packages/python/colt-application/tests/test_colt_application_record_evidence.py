from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.use_cases.record_evidence import RecordEvidence
from colt_domain import Evidence, VerificationStatus


class FakeEvidenceRepository:
    """Only `add` is exercised; `get`/`list_by_entity` exist purely so this structurally
    satisfies the `EvidenceRepository` port (Milestone 15 added both)."""

    def __init__(self) -> None:
        self.added: list[Evidence] = []

    async def add(self, **kwargs: object) -> Evidence:
        evidence = Evidence(
            id=uuid4(),
            organization_id=uuid4(),
            created_at=datetime.now(UTC),
            **kwargs,  # type: ignore[arg-type]
        )
        self.added.append(evidence)
        return evidence

    async def get(self, evidence_id: UUID) -> Evidence | None:
        raise NotImplementedError

    async def list_by_entity(self, entity_type: str, entity_id: UUID) -> list[Evidence]:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_records_a_fresh_claim_as_unverified() -> None:
    repo = FakeEvidenceRepository()
    record = RecordEvidence(repo)

    evidence = await record(
        entity_type="Company",
        entity_id=uuid4(),
        claim="Acme raised a $10M Series A.",
        source_url="https://acme.example/news",
        observed_at=datetime.now(UTC),
        source_date=date.today(),
    )

    assert evidence.verification_status == VerificationStatus.UNVERIFIED
    assert evidence.claim == "Acme raised a $10M Series A."
    assert repo.added == [evidence]


@pytest.mark.asyncio
async def test_records_an_old_claim_as_stale() -> None:
    repo = FakeEvidenceRepository()
    record = RecordEvidence(repo)

    evidence = await record(
        entity_type="Company",
        entity_id=uuid4(),
        claim="Acme raised a $10M Series A.",
        source_url="https://acme.example/news",
        observed_at=datetime.now(UTC),
        source_date=date(2020, 1, 1),
    )

    assert evidence.verification_status == VerificationStatus.STALE
