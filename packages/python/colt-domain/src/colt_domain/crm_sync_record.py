"""The CrmSyncRecord entity (CLAUDE.md §30) — "Colt remains system of record for Colt-native
workflow state," CRM is "a synchronized external system" — this is the one row that tracks how
one Colt entity maps to one external CRM object, never a column on the entities themselves.

Polymorphic (`entity_type` + `entity_id`), the same reasoning `Evidence` (§10.6) already
establishes: any syncable entity (`Company`, `Person`, `Opportunity`, and a CRM "task," which
Colt itself has no native entity for yet) can be the subject, rather than a foreign key to one
table. CLAUDE.md names the exact fields to store ("provider name, provider account ID, provider
object ID, last synced at, sync status, last error") but no entity name or `sync_status`
vocabulary — this milestone's own documented design decision, the same reasoning `CampaignStatus`
(Milestone 14) and `Urgency` (Milestone 19) already apply.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class SyncStatus(StrEnum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"


class CrmSyncRecord(BaseModel):
    """How one Colt entity maps to one external CRM provider's object, and the outcome of the
    last attempt to keep them in sync."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    entity_type: str
    entity_id: UUID
    provider_name: str
    provider_account_id: str
    provider_object_id: str | None = None
    sync_status: SyncStatus = SyncStatus.PENDING
    last_synced_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("entity_type", "provider_name", "provider_account_id")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "CrmSyncRecord entity_type, provider_name and provider_account_id must not be "
                "blank."
            )
        return value

    def synced(self, *, provider_object_id: str, at: datetime) -> Self:
        return self.model_copy(
            update={
                "provider_object_id": provider_object_id,
                "sync_status": SyncStatus.SYNCED,
                "last_synced_at": at,
                "last_error": None,
                "updated_at": at,
            }
        )

    def failed(self, *, error: str, at: datetime) -> Self:
        return self.model_copy(
            update={"sync_status": SyncStatus.FAILED, "last_error": error, "updated_at": at}
        )
