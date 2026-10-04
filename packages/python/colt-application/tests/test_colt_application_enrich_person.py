from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.use_cases.enrich_person import EnrichPerson
from colt_domain import EmailStatus, Person


class FakePersonRepository:
    """Only `get`/`update` are exercised; the other `PersonRepository` methods exist purely so
    this structurally satisfies the port."""

    def __init__(self, seed: Person) -> None:
        self.rows: dict[UUID, Person] = {seed.id: seed}

    async def add(self, **kwargs: Any) -> Person:
        raise NotImplementedError

    async def get(self, person_id: UUID) -> Person | None:
        return self.rows.get(person_id)

    async def find_by_email(self, email: str) -> Person | None:
        raise NotImplementedError

    async def find_by_linkedin_url(self, linkedin_url: str) -> Person | None:
        raise NotImplementedError

    async def list_by_company(self, company_id: UUID) -> list[Person]:
        raise NotImplementedError

    async def find_by_provider_id(self, provider: str, provider_id: str) -> Person | None:
        raise NotImplementedError

    async def update(self, person_id: UUID, **fields: Any) -> Person:
        existing = self.rows[person_id]
        updated = existing.model_copy(update={k: v for k, v in fields.items() if v is not None})
        self.rows[person_id] = updated
        return updated


def _person(**overrides: Any) -> Person:
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": uuid4(),
        "company_id": uuid4(),
        "full_name": "Jane Doe",
        "source_metadata": {"provider": "fake", "provider_id": None, "confidence": 0.5},
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Person(**defaults)


@pytest.mark.asyncio
async def test_a_higher_confidence_candidate_sets_email_and_verified_status() -> None:
    person = _person()
    repo = FakePersonRepository(person)
    enrich = EnrichPerson(repo)

    updated = await enrich(
        person.id,
        provider="apollo",
        confidence=0.9,
        email="Jane.Doe@Acme.example",
        email_verified=True,
    )

    assert updated.email == "jane.doe@acme.example"
    assert updated.email_status == EmailStatus.VALID


@pytest.mark.asyncio
async def test_an_unconfirmed_email_status_maps_to_unknown_not_invalid() -> None:
    person = _person()
    repo = FakePersonRepository(person)
    enrich = EnrichPerson(repo)

    updated = await enrich(
        person.id,
        provider="apollo",
        confidence=0.9,
        email="jane@acme.example",
        email_verified=False,
    )

    assert updated.email_status == EmailStatus.UNKNOWN


@pytest.mark.asyncio
async def test_a_lower_confidence_candidate_is_a_no_op() -> None:
    person = _person(email="jane@acme.example")
    repo = FakePersonRepository(person)
    enrich = EnrichPerson(repo)

    updated = await enrich(person.id, provider="brave", confidence=0.1, email="wrong@acme.example")

    assert updated.email == "jane@acme.example"
