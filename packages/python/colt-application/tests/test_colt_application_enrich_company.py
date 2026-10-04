from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.use_cases.enrich_company import EnrichCompany
from colt_domain import Company


class FakeCompanyRepository:
    """Only `get`/`update` are exercised; the other `CompanyRepository` methods exist purely so
    this structurally satisfies the port."""

    def __init__(self, seed: Company) -> None:
        self.rows: dict[UUID, Company] = {seed.id: seed}

    async def add(self, **kwargs: Any) -> Company:
        raise NotImplementedError

    async def get(self, company_id: UUID) -> Company | None:
        return self.rows.get(company_id)

    async def find_by_normalized_domain(self, normalized_domain: str) -> Company | None:
        raise NotImplementedError

    async def find_by_linkedin_url(self, linkedin_url: str) -> Company | None:
        raise NotImplementedError

    async def find_by_provider_id(self, provider: str, provider_id: str) -> Company | None:
        raise NotImplementedError

    async def update(self, company_id: UUID, **fields: Any) -> Company:
        existing = self.rows[company_id]
        updated = existing.model_copy(update={k: v for k, v in fields.items() if v is not None})
        self.rows[company_id] = updated
        return updated


def _company(**overrides: Any) -> Company:
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": uuid4(),
        "name": "Acme Rockets",
        "source_metadata": {"provider": "fake", "provider_id": None, "confidence": 0.5},
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Company(**defaults)


@pytest.mark.asyncio
async def test_a_higher_confidence_candidate_overwrites_fields() -> None:
    company = _company()
    repo = FakeCompanyRepository(company)
    enrich = EnrichCompany(repo)

    updated = await enrich(
        company.id, provider="apollo", confidence=0.9, employee_count=250, industry="Aerospace"
    )

    assert updated.employee_count == 250
    assert updated.industry == "Aerospace"
    assert updated.source_metadata["confidence"] == 0.9


@pytest.mark.asyncio
async def test_a_lower_confidence_candidate_is_a_no_op() -> None:
    company = _company(employee_count=100)
    repo = FakeCompanyRepository(company)
    enrich = EnrichCompany(repo)

    updated = await enrich(company.id, provider="brave", confidence=0.1, employee_count=999)

    assert updated.employee_count == 100
    assert updated.source_metadata["confidence"] == 0.5
