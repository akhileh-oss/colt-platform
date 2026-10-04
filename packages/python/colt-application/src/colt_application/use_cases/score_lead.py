"""`ScoreLead` (CLAUDE.md §10.8, §12.7, §21) — the use case `colt-agents`' `score_lead` tool
calls.

Computes `overall_score`/`reason_codes` itself rather than trusting a caller-supplied value —
same reasoning `RecordEvidence`'s `verification_status` computation gives: these are the kind
of deterministic facts §2.1 reserves for application code, not model judgment, even though one
of the five inputs that feeds them (`model_assessment`) is itself the model's judgment. Writes
exactly one new `LeadScore` row (never overwrites history, §10.8) and transitions the `Lead`'s
`status` to whatever `determine_qualification()` decides.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.ports.lead_repository import LeadRepository
from colt_application.ports.lead_score_repository import LeadScoreRepository
from colt_application.scoring import (
    SCORE_MODEL_VERSION,
    compute_overall_score,
    determine_qualification,
    determine_reason_codes,
)
from colt_domain import Lead, LeadScore


class ScoreLead:
    def __init__(self, lead_scores: LeadScoreRepository, leads: LeadRepository) -> None:
        self._lead_scores = lead_scores
        self._leads = leads

    async def __call__(
        self,
        *,
        lead_id: UUID,
        icp_fit: float,
        persona_fit: float,
        signal_strength: float,
        timing: float,
        model_assessment: float,
        confidence: float | None = None,
        now: datetime,
    ) -> tuple[LeadScore, Lead]:
        overall_score = compute_overall_score(
            icp_fit=icp_fit,
            persona_fit=persona_fit,
            signal_strength=signal_strength,
            timing=timing,
            model_assessment=model_assessment,
        )
        reason_codes = determine_reason_codes(
            icp_fit=icp_fit,
            persona_fit=persona_fit,
            signal_strength=signal_strength,
            timing=timing,
            overall_score=overall_score,
        )
        score = await self._lead_scores.add(
            lead_id=lead_id,
            model_version=SCORE_MODEL_VERSION,
            icp_fit=icp_fit,
            persona_fit=persona_fit,
            signal_strength=signal_strength,
            timing=timing,
            model_assessment=model_assessment,
            overall_score=overall_score,
            reason_codes=reason_codes,
            confidence=confidence,
        )
        qualification = determine_qualification(overall_score)
        lead = await self._leads.update_status(lead_id, qualification, at=now)
        return score, lead
