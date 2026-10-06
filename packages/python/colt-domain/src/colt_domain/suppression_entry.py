"""The SuppressionEntry entity (CLAUDE.md §10.18) — an explicit, global outbound-suppression
record. "Global outbound suppression must be modeled explicitly" and "No campaign or agent may
override a suppression entry" (§18.1).

`organization_id` is nullable "for system-wide policy" per §10.18 itself — a suppression entry
with no organization applies across every tenant (e.g. a legal takedown), while a normal
unsubscribe/bounce is scoped to the one organization that owns the relationship.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class SuppressionReason(StrEnum):
    """The closed set of reasons §10.18 itself enumerates."""

    UNSUBSCRIBE = "unsubscribe"
    BOUNCE = "bounce"
    SPAM_COMPLAINT = "spam_complaint"
    MANUAL_BLOCK = "manual_block"
    LEGAL_REQUEST = "legal_request"
    DO_NOT_CONTACT = "do_not_contact"


class SuppressionEntry(BaseModel):
    """One identifier (an email address, a phone number, ...) that must never be contacted
    again through the channel(s) its `identifier_type` governs."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID | None = None
    identifier_type: str
    identifier: str
    reason: SuppressionReason
    source: str
    created_at: datetime
    updated_at: datetime

    @field_validator("identifier_type", "identifier", "source")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "SuppressionEntry identifier_type, identifier and source must not be blank."
            )
        return value
