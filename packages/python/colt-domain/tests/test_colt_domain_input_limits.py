"""Free-text field length limits (CLAUDE.md §40, Milestone 24) — `Campaign.name`, `Company.name`
/`description`, `Person.full_name`, and `Message.subject`/`body` each reject a value past their
own documented bound, matching (where one exists) the backing database column's own width
exactly, so the domain layer never claims a looser limit than Postgres actually enforces.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from colt_domain import Campaign, Company, Message, Person

NOW = datetime.now(UTC)


def test_campaign_name_over_300_characters_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Campaign(
            id=uuid4(), organization_id=uuid4(), name="x" * 301, created_at=NOW, updated_at=NOW
        )


def test_campaign_name_at_exactly_300_characters_is_accepted() -> None:
    campaign = Campaign(
        id=uuid4(), organization_id=uuid4(), name="x" * 300, created_at=NOW, updated_at=NOW
    )
    assert len(campaign.name) == 300


def test_company_name_over_300_characters_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Company(id=uuid4(), organization_id=uuid4(), name="x" * 301, created_at=NOW, updated_at=NOW)


def test_company_description_over_5000_characters_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Company(
            id=uuid4(),
            organization_id=uuid4(),
            name="Acme",
            description="x" * 5_001,
            created_at=NOW,
            updated_at=NOW,
        )


def test_person_full_name_over_300_characters_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Person(
            id=uuid4(),
            organization_id=uuid4(),
            company_id=uuid4(),
            full_name="x" * 301,
            created_at=NOW,
            updated_at=NOW,
        )


def test_message_subject_over_500_characters_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Message(
            id=uuid4(),
            organization_id=uuid4(),
            campaign_id=uuid4(),
            lead_id=uuid4(),
            channel="email",
            subject="x" * 501,
            body="hello",
            created_at=NOW,
            updated_at=NOW,
        )


def test_message_body_over_100_000_characters_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Message(
            id=uuid4(),
            organization_id=uuid4(),
            campaign_id=uuid4(),
            lead_id=uuid4(),
            channel="email",
            body="x" * 100_001,
            created_at=NOW,
            updated_at=NOW,
        )


def test_message_body_at_exactly_100_000_characters_is_accepted() -> None:
    message = Message(
        id=uuid4(),
        organization_id=uuid4(),
        campaign_id=uuid4(),
        lead_id=uuid4(),
        channel="email",
        body="x" * 100_000,
        created_at=NOW,
        updated_at=NOW,
    )
    assert len(message.body) == 100_000
