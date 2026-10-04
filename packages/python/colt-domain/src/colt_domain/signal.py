"""The Signal entity (CLAUDE.md §10.5) — a reason a company/person's business conditions may
be changing (funding, leadership change, hiring, expansion, ...).

`signal_type` is stored as free text, not a closed enum: §10.5 introduces its list of types with
"Examples", unlike the closed state machines in §11 ("Do not let LLMs invent arbitrary statuses"),
so new signal types are expected to be added over time without a migration.

`business_implication` (Milestone 11 did not add it; Milestone 12's `SignalAgent` is the first
thing that populates it) is §12.6's required output field explaining what a signal means for
sales strategy — judgment, not a deterministic computation (§2.1), so unlike
`verification_status`/`email_status` it is never server-computed and is simply stored as the
model gives it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class Signal(BaseModel):
    """A why-now event observed about a company, optionally attributed to one person."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    company_id: UUID
    person_id: UUID | None = None
    signal_type: str
    source_url: str | None = None
    source_type: str | None = None
    observed_at: datetime
    event_at: datetime | None = None
    confidence: float | None = None
    summary: str | None = None
    business_implication: str | None = None
    raw_payload: dict[str, Any] = {}
    created_at: datetime

    @field_validator("signal_type")
    @classmethod
    def _signal_type_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("signal_type must not be blank.")
        return value

    @field_validator("confidence")
    @classmethod
    def _confidence_in_unit_range(cls, value: float | None) -> float | None:
        if value is not None and not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0.")
        return value
