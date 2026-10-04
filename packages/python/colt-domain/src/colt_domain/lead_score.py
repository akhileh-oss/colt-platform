"""The LeadScore entity (CLAUDE.md §10.8) — one immutable, append-only scoring evaluation.

"Do not overwrite scoring history. Use immutable or append-only score evaluations where
practical." There is no `update`/`with_*` method here and no `updated_at` field — a new score
is always a new row (`colt_application.use_cases.score_lead.ScoreLead`), never a mutation of an
existing one, so `created_at` alone is enough to order a lead's history.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class LeadScore(BaseModel):
    """One scoring evaluation of a `Lead`, versioned by the rules/weights that produced it."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    lead_id: UUID
    model_version: str
    icp_fit: float
    persona_fit: float
    signal_strength: float
    timing: float
    model_assessment: float
    overall_score: float
    reason_codes: list[str]
    confidence: float | None = None
    created_at: datetime

    @field_validator(
        "icp_fit", "persona_fit", "signal_strength", "timing", "model_assessment", "overall_score"
    )
    @classmethod
    def _component_in_unit_range(cls, value: float) -> float:
        if not (0.0 <= value <= 1.0):
            raise ValueError("score components must be between 0.0 and 1.0.")
        return value

    @field_validator("confidence")
    @classmethod
    def _confidence_in_unit_range(cls, value: float | None) -> float | None:
        if value is not None and not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0.")
        return value
