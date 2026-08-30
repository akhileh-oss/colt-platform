"""The Opportunity entity (CLAUDE.md §10.14) — a commercial opportunity.

`PipelineStage` is the closed state machine from §11.3: an explicit deterministic pipeline with
minimum lifecycle support (`CLAUDE.md` §11.3 notes an organization may configure its own pipeline
on top of this; this enum is the required minimum, not the ceiling).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PipelineStage(StrEnum):
    QUALIFIED = "QUALIFIED"
    DISCOVERY = "DISCOVERY"
    EVALUATION = "EVALUATION"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"


class Opportunity(BaseModel):
    """A commercial opportunity, usually originating from a `Lead`."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    company_id: UUID
    primary_person_id: UUID | None = None
    lead_id: UUID | None = None
    pipeline_stage: PipelineStage = PipelineStage.QUALIFIED
    estimated_value: float | None = None
    currency: str | None = None
    probability: float | None = None
    owner_id: UUID | None = None
    source: str | None = None
    created_at: datetime
    updated_at: datetime

    def with_stage(self, stage: PipelineStage, *, at: datetime) -> Self:
        return self.model_copy(update={"pipeline_stage": stage, "updated_at": at})
