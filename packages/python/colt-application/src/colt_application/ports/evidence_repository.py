"""The Evidence repository port (CLAUDE.md §2.3, §10.6, §20).

Tenant-scoped, like `LeadRepository`: an implementation is bound to one `organization_id` at
construction.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from colt_domain import Evidence, VerificationStatus


class EvidenceRepository(Protocol):
    async def add(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        claim: str,
        source_url: str,
        observed_at: datetime,
        source_type: str | None = None,
        source_date: date | None = None,
        excerpt: str | None = None,
        confidence: float | None = None,
        verification_status: VerificationStatus = VerificationStatus.UNVERIFIED,
    ) -> Evidence: ...
