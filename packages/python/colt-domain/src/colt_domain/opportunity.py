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
    #: True whenever `estimated_value` was supplied by a model's own judgment rather than a
    #: configured source/rule Colt trusts outright — CLAUDE.md §12.11's "estimates must be
    #: labeled estimates" for `OpportunityAgent` (Milestone 21). No configured override source
    #: exists in this environment, so every model-supplied value is always an estimate; this
    #: field exists so a later milestone that does add one has somewhere to record the
    #: distinction rather than needing a schema change.
    is_estimated_value: bool = False
    created_at: datetime
    updated_at: datetime

    def with_stage(self, stage: PipelineStage, *, at: datetime) -> Self:
        return self.model_copy(update={"pipeline_stage": stage, "updated_at": at})

    def with_owner(self, owner_id: UUID, *, at: datetime) -> Self:
        return self.model_copy(update={"owner_id": owner_id, "updated_at": at})

    def with_value(
        self, *, estimated_value: float, currency: str, is_estimate: bool, at: datetime
    ) -> Self:
        return self.model_copy(
            update={
                "estimated_value": estimated_value,
                "currency": currency,
                "is_estimated_value": is_estimate,
                "updated_at": at,
            }
        )
