"""Tenant-scoped repository for `Evidence` (CLAUDE.md §10.6)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from colt_db.mappers import evidence_to_domain
from colt_db.models.evidence import EvidenceModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import Evidence


class SqlAlchemyEvidenceRepository(TenantScopedRepository):
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
        verification_status: str = "UNVERIFIED",
    ) -> Evidence:
        model = EvidenceModel(
            organization_id=self.organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            claim=claim,
            source_url=source_url,
            source_type=source_type,
            source_date=source_date,
            observed_at=observed_at,
            excerpt=excerpt,
            confidence=confidence,
            verification_status=verification_status,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return evidence_to_domain(model)

    async def get(self, evidence_id: UUID) -> Evidence | None:
        stmt = self._select_scoped(EvidenceModel).where(EvidenceModel.id == evidence_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return evidence_to_domain(model) if model is not None else None
