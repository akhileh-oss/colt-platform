from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.use_cases.discover_company import DiscoverCompany
from colt_domain import Company


class FakeCompanyRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Company] = {}

    async def add(self, **kwargs: Any) -> Company:
        company = Company(
            id=uuid4(),
            organization_id=uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            **kwargs,
        )
        self.rows[company.id] = company
        return company

    async def get(self, company_id: UUID) -> Company | None:
        return self.rows.get(company_id)

    async def find_by_normalized_domain(self, normalized_domain: str) -> Company | None:
        return next(
            (c for c in self.rows.values() if c.normalized_domain == normalized_domain), None
        )

    async def find_by_linkedin_url(self, linkedin_url: str) -> Company | None:
        return next((c for c in self.rows.values() if c.linkedin_url == linkedin_url), None)

    async def find_by_provider_id(self, provider: str, provider_id: str) -> Company | None:
        return next(
            (
                c
                for c in self.rows.values()
                if c.source_metadata.get("provider") == provider
                and c.source_metadata.get("provider_id") == provider_id
            ),
            None,
        )

    async def update(self, company_id: UUID, **fields: Any) -> Company:
        existing = self.rows[company_id]
        updated = existing.model_copy(update={k: v for k, v in fields.items() if v is not None})
        self.rows[company_id] = updated
        return updated


@pytest.mark.asyncio
async def test_a_new_candidate_creates_a_company_with_source_metadata() -> None:
    repo = FakeCompanyRepository()
    discover = DiscoverCompany(repo)

    company, created = await discover(
        name="Acme Rockets",
        provider="apollo",
        confidence=0.9,
        provider_id="org_1",
        domain="https://www.acme.example",
    )

    assert created is True
    assert company.normalized_domain == "acme.example"
    assert company.source_metadata == {
        "provider": "apollo",
        "provider_id": "org_1",
        "confidence": 0.9,
    }


@pytest.mark.asyncio
async def test_a_second_candidate_with_the_same_provider_id_deduplicates() -> None:
    repo = FakeCompanyRepository()
    discover = DiscoverCompany(repo)

    first, _ = await discover(
        name="Acme Rockets", provider="apollo", confidence=0.9, provider_id="org_1"
    )
    second, created = await discover(
        name="Acme Rockets Inc.", provider="apollo", confidence=0.95, provider_id="org_1"
    )

    assert created is False
    assert second.id == first.id
    assert len(repo.rows) == 1


@pytest.mark.asyncio
async def test_a_second_candidate_with_the_same_normalized_domain_deduplicates() -> None:
    repo = FakeCompanyRepository()
    discover = DiscoverCompany(repo)

    first, _ = await discover(
        name="Acme Rockets", provider="apollo", confidence=0.9, domain="acme.example"
    )
    second, created = await discover(
        name="Acme Rockets", provider="brave", confidence=0.5, domain="https://www.acme.example/"
    )

    assert created is False
    assert second.id == first.id
    assert len(repo.rows) == 1


@pytest.mark.asyncio
async def test_distinct_domains_never_merge() -> None:
    repo = FakeCompanyRepository()
    discover = DiscoverCompany(repo)

    first, _ = await discover(
        name="Acme Rockets", provider="apollo", confidence=0.9, domain="acme.example"
    )
    second, created = await discover(
        name="Acme Rockets Europe", provider="apollo", confidence=0.9, domain="acme.eu"
    )

    assert created is True
    assert second.id != first.id
    assert len(repo.rows) == 2
