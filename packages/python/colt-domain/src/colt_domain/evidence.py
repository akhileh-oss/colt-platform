"""The Evidence entity (CLAUDE.md §10.6) — a sourced, dated, confidence-scored claim.

Evidence is polymorphic (`entity_type` + `entity_id`, e.g. a Company or a Signal) rather than a
foreign key to one table, since any evidence-bearing entity can be a claim's subject. Every
outbound claim must trace to one of these, never an invented source (§2.6).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class Evidence(BaseModel):
    """A single sourced, dated claim about some entity, with a confidence and verification state."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    entity_type: str
    entity_id: UUID
    claim: str
    source_url: str
    source_type: str | None = None
    source_date: date | None = None
    observed_at: datetime
    excerpt: str | None = None
    confidence: float | None = None
    verification_status: str = "UNVERIFIED"
    created_at: datetime

    @field_validator("entity_type")
    @classmethod
    def _entity_type_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("entity_type must not be blank.")
        return value

    @field_validator("claim")
    @classmethod
    def _claim_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Evidence claim must not be blank.")
        return value

    @field_validator("source_url")
    @classmethod
    def _source_url_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "Evidence must carry a source_url — an unsourced claim is not evidence."
            )
        return value

    @field_validator("confidence")
    @classmethod
    def _confidence_in_unit_range(cls, value: float | None) -> float | None:
        if value is not None and not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0.")
        return value
