"""Tenant-scoped repository for `LeadScore` (CLAUDE.md §10.8) — append-only; no `update`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc

from colt_db.mappers import lead_score_to_domain
from colt_db.models.lead_score import LeadScoreModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import LeadScore


class SqlAlchemyLeadScoreRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        lead_id: UUID,
        model_version: str,
        icp_fit: float,
        persona_fit: float,
        signal_strength: float,
        timing: float,
        model_assessment: float,
        overall_score: float,
        reason_codes: list[str],
        confidence: float | None = None,
    ) -> LeadScore:
        model = LeadScoreModel(
            organization_id=self.organization_id,
            lead_id=lead_id,
            model_version=model_version,
            icp_fit=icp_fit,
            persona_fit=persona_fit,
            signal_strength=signal_strength,
            timing=timing,
            model_assessment=model_assessment,
            overall_score=overall_score,
            reason_codes=reason_codes,
            confidence=confidence,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return lead_score_to_domain(model)

    async def get(self, lead_score_id: UUID) -> LeadScore | None:
        stmt = self._select_scoped(LeadScoreModel).where(LeadScoreModel.id == lead_score_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return lead_score_to_domain(model) if model is not None else None

    async def list_by_lead(self, lead_id: UUID) -> list[LeadScore]:
        """Newest first - the full, unmodified scoring history for one lead."""
        stmt = (
            self._select_scoped(LeadScoreModel)
            .where(LeadScoreModel.lead_id == lead_id)
            .order_by(desc(LeadScoreModel.created_at))
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [lead_score_to_domain(model) for model in models]
