from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.use_cases.discover_person import DiscoverPerson
from colt_domain import Person


class FakePersonRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Person] = {}

    async def add(self, **kwargs: Any) -> Person:
        person = Person(
            id=uuid4(),
            organization_id=uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            **kwargs,
        )
        self.rows[person.id] = person
        return person

    async def get(self, person_id: UUID) -> Person | None:
        return self.rows.get(person_id)

    async def find_by_email(self, email: str) -> Person | None:
        return next((p for p in self.rows.values() if p.email == email), None)

    async def find_by_linkedin_url(self, linkedin_url: str) -> Person | None:
        return next((p for p in self.rows.values() if p.linkedin_url == linkedin_url), None)

    async def find_by_provider_id(self, provider: str, provider_id: str) -> Person | None:
        return next(
            (
                p
                for p in self.rows.values()
                if p.source_metadata.get("provider") == provider
                and p.source_metadata.get("provider_id") == provider_id
            ),
            None,
        )

    async def list_by_company(self, company_id: UUID) -> list[Person]:
        return [p for p in self.rows.values() if p.company_id == company_id]

    async def update(self, person_id: UUID, **fields: Any) -> Person:
        existing = self.rows[person_id]
        updated = existing.model_copy(update={k: v for k, v in fields.items() if v is not None})
        self.rows[person_id] = updated
        return updated


@pytest.mark.asyncio
async def test_a_new_candidate_creates_a_person_with_source_metadata() -> None:
    repo = FakePersonRepository()
    discover = DiscoverPerson(repo)
    company_id = uuid4()

    person, created = await discover(
        company_id=company_id,
        full_name="Jane Doe",
        provider="apollo",
        confidence=0.9,
        email="Jane.Doe@Acme.example",
    )

    assert created is True
    assert person.email == "jane.doe@acme.example"
    assert person.source_metadata["provider"] == "apollo"


@pytest.mark.asyncio
async def test_a_second_candidate_with_the_same_email_deduplicates() -> None:
    repo = FakePersonRepository()
    discover = DiscoverPerson(repo)
    company_id = uuid4()

    first, _ = await discover(
        company_id=company_id,
        full_name="Jane Doe",
        provider="apollo",
        confidence=0.9,
        email="jane@acme.example",
    )
    second, created = await discover(
        company_id=company_id,
        full_name="Jane D.",
        provider="brave",
        confidence=0.4,
        email="Jane@Acme.example",
    )

    assert created is False
    assert second.id == first.id


@pytest.mark.asyncio
async def test_a_high_confidence_candidate_matches_by_company_and_normalized_name() -> None:
    repo = FakePersonRepository()
    discover = DiscoverPerson(repo)
    company_id = uuid4()

    first, _ = await discover(
        company_id=company_id, full_name="Jane Doe", provider="apollo", confidence=0.9
    )
    second, created = await discover(
        company_id=company_id, full_name="  jane   doe ", provider="brave", confidence=0.8
    )

    assert created is False
    assert second.id == first.id


@pytest.mark.asyncio
async def test_a_low_confidence_candidate_never_matches_by_name_alone() -> None:
    repo = FakePersonRepository()
    discover = DiscoverPerson(repo)
    company_id = uuid4()

    first, _ = await discover(
        company_id=company_id, full_name="Jane Doe", provider="apollo", confidence=0.9
    )
    second, created = await discover(
        company_id=company_id, full_name="Jane Doe", provider="brave", confidence=0.5
    )

    assert created is True
    assert second.id != first.id


@pytest.mark.asyncio
async def test_different_companies_never_merge_on_name() -> None:
    repo = FakePersonRepository()
    discover = DiscoverPerson(repo)

    first, _ = await discover(
        company_id=uuid4(), full_name="Jane Doe", provider="apollo", confidence=0.9
    )
    second, created = await discover(
        company_id=uuid4(), full_name="Jane Doe", provider="apollo", confidence=0.9
    )

    assert created is True
    assert second.id != first.id
