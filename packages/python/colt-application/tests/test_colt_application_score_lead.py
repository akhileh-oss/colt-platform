from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.use_cases.score_lead import ScoreLead
from colt_domain import Lead, LeadScore, LeadStatus

NOW = datetime.now(UTC)


class FakeLeadScoreRepository:
    def __init__(self) -> None:
        self.added: list[LeadScore] = []

    async def add(self, **kwargs: Any) -> LeadScore:
        score = LeadScore(id=uuid4(), organization_id=uuid4(), created_at=NOW, **kwargs)
        self.added.append(score)
        return score

    async def get(self, lead_score_id: UUID) -> LeadScore | None:
        return next((s for s in self.added if s.id == lead_score_id), None)

    async def list_by_lead(self, lead_id: UUID) -> list[LeadScore]:
        return [s for s in self.added if s.lead_id == lead_id]


class FakeLeadRepository:
    def __init__(self, lead: Lead) -> None:
        self.lead = lead
        self.status_updates: list[LeadStatus] = []

    async def get(self, lead_id: UUID) -> Lead | None:
        return self.lead if lead_id == self.lead.id else None

    async def update_status(self, lead_id: UUID, status: LeadStatus, *, at: datetime) -> Lead:
        self.status_updates.append(status)
        self.lead = self.lead.with_status(status, at=at)
        return self.lead


def _lead() -> Lead:
    return Lead(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        person_id=uuid4(),
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_a_high_scoring_lead_is_persisted_and_qualified() -> None:
    lead = _lead()
    lead_scores = FakeLeadScoreRepository()
    leads = FakeLeadRepository(lead)
    score_lead = ScoreLead(lead_scores, leads)

    score, updated_lead = await score_lead(
        lead_id=lead.id,
        icp_fit=0.9,
        persona_fit=0.9,
        signal_strength=0.9,
        timing=0.9,
        model_assessment=0.9,
        now=NOW,
    )

    assert score.overall_score == pytest.approx(0.9)
    assert "MEETS_QUALIFICATION_THRESHOLD" in score.reason_codes
    assert updated_lead.status == LeadStatus.QUALIFIED
    assert leads.status_updates == [LeadStatus.QUALIFIED]


@pytest.mark.asyncio
async def test_a_low_scoring_lead_is_persisted_and_not_qualified() -> None:
    lead = _lead()
    lead_scores = FakeLeadScoreRepository()
    leads = FakeLeadRepository(lead)
    score_lead = ScoreLead(lead_scores, leads)

    score, updated_lead = await score_lead(
        lead_id=lead.id,
        icp_fit=0.1,
        persona_fit=0.1,
        signal_strength=0.1,
        timing=0.1,
        model_assessment=0.1,
        now=NOW,
    )

    assert "BELOW_QUALIFICATION_THRESHOLD" in score.reason_codes
    assert updated_lead.status == LeadStatus.NOT_QUALIFIED


@pytest.mark.asyncio
async def test_scoring_the_same_lead_twice_appends_history_rather_than_overwriting() -> None:
    lead = _lead()
    lead_scores = FakeLeadScoreRepository()
    leads = FakeLeadRepository(lead)
    score_lead = ScoreLead(lead_scores, leads)

    await score_lead(
        lead_id=lead.id,
        icp_fit=0.2,
        persona_fit=0.2,
        signal_strength=0.2,
        timing=0.2,
        model_assessment=0.2,
        now=NOW,
    )
    await score_lead(
        lead_id=lead.id,
        icp_fit=0.9,
        persona_fit=0.9,
        signal_strength=0.9,
        timing=0.9,
        model_assessment=0.9,
        now=NOW,
    )

    history = await lead_scores.list_by_lead(lead.id)
    assert len(history) == 2
    assert history[0].overall_score != history[1].overall_score
