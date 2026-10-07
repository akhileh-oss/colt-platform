"""Deterministic funnel summary (CLAUDE.md §68, Milestone 22)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from colt_application.funnel import summarize_funnel
from colt_domain import Lead, LeadStatus

NOW = datetime.now(UTC)


def _lead(*, status: LeadStatus) -> Lead:
    return Lead(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        person_id=uuid4(),
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


def test_every_lead_status_is_present_even_with_no_leads_in_it() -> None:
    rows = summarize_funnel([])

    assert {row.status for row in rows} == set(LeadStatus)
    assert all(row.count == 0 for row in rows)


def test_rows_are_in_lead_status_declaration_order() -> None:
    rows = summarize_funnel([])

    assert [row.status for row in rows] == list(LeadStatus)


def test_counts_leads_per_status() -> None:
    leads = [
        _lead(status=LeadStatus.NEW),
        _lead(status=LeadStatus.NEW),
        _lead(status=LeadStatus.QUALIFIED),
    ]

    rows = {row.status: row.count for row in summarize_funnel(leads)}

    assert rows[LeadStatus.NEW] == 2
    assert rows[LeadStatus.QUALIFIED] == 1
    assert rows[LeadStatus.ENGAGED] == 0
