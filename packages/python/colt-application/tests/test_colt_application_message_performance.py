"""Deterministic message-performance summary (CLAUDE.md §68, Milestone 22)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from colt_application.message_performance import summarize_message_performance
from colt_domain import Lead, LeadStatus, Message, Person

NOW = datetime.now(UTC)


def _lead(*, person_id: UUID) -> Lead:
    return Lead(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        person_id=person_id,
        status=LeadStatus.NEW,
        created_at=NOW,
        updated_at=NOW,
    )


def _person(*, seniority: str | None) -> Person:
    return Person(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        full_name="Jane Doe",
        seniority=seniority,
        created_at=NOW,
        updated_at=NOW,
    )


def _message(
    *,
    lead_id: UUID,
    prompt_version: str | None,
    status: str = "DRAFT",
    approval_status: str = "PENDING",
) -> Message:
    return Message(
        id=uuid4(),
        organization_id=uuid4(),
        campaign_id=uuid4(),
        lead_id=lead_id,
        channel="email",
        body="hello",
        prompt_version=prompt_version,
        status=status,
        approval_status=approval_status,
        created_at=NOW,
        updated_at=NOW,
    )


def test_groups_by_prompt_version_and_persona() -> None:
    person = _person(seniority="VP")
    lead = _lead(person_id=person.id)
    messages = [
        _message(lead_id=lead.id, prompt_version="v1"),
        _message(lead_id=lead.id, prompt_version="v1"),
        _message(lead_id=lead.id, prompt_version="v2"),
    ]

    rows = {
        (row.prompt_version, row.persona): row
        for row in summarize_message_performance(messages, [lead], [person])
    }

    assert rows[("v1", "VP")].drafted_count == 2
    assert rows[("v2", "VP")].drafted_count == 1


def test_missing_prompt_version_falls_back_to_unknown() -> None:
    person = _person(seniority="VP")
    lead = _lead(person_id=person.id)
    messages = [_message(lead_id=lead.id, prompt_version=None)]

    rows = summarize_message_performance(messages, [lead], [person])

    assert rows[0].prompt_version == "unknown"


def test_person_with_no_seniority_falls_back_to_unknown_persona() -> None:
    person = _person(seniority=None)
    lead = _lead(person_id=person.id)
    messages = [_message(lead_id=lead.id, prompt_version="v1")]

    rows = summarize_message_performance(messages, [lead], [person])

    assert rows[0].persona == "unknown"


def test_message_whose_lead_is_not_found_falls_back_to_unknown_persona() -> None:
    messages = [_message(lead_id=uuid4(), prompt_version="v1")]

    rows = summarize_message_performance(messages, [], [])

    assert rows[0].persona == "unknown"


def test_counts_sent_and_approved_messages() -> None:
    person = _person(seniority="VP")
    lead = _lead(person_id=person.id)
    messages = [
        _message(lead_id=lead.id, prompt_version="v1", status="SENT", approval_status="APPROVED"),
        _message(lead_id=lead.id, prompt_version="v1", status="DRAFT", approval_status="PENDING"),
    ]

    rows = summarize_message_performance(messages, [lead], [person])

    assert rows[0].drafted_count == 2
    assert rows[0].sent_count == 1
    assert rows[0].approved_count == 1
