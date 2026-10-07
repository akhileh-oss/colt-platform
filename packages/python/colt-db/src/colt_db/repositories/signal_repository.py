"""Tenant-scoped repository for `Signal` (CLAUDE.md §10.5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from colt_db.mappers import signal_to_domain
from colt_db.models.signal import SignalModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import Signal


class SqlAlchemySignalRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        company_id: UUID,
        signal_type: str,
        observed_at: datetime,
        person_id: UUID | None = None,
        source_url: str | None = None,
        source_type: str | None = None,
        event_at: datetime | None = None,
        confidence: float | None = None,
        summary: str | None = None,
        business_implication: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> Signal:
        model = SignalModel(
            organization_id=self.organization_id,
            company_id=company_id,
            person_id=person_id,
            signal_type=signal_type,
            source_url=source_url,
            source_type=source_type,
            observed_at=observed_at,
            event_at=event_at,
            confidence=confidence,
            summary=summary,
            business_implication=business_implication,
            raw_payload=raw_payload or {},
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return signal_to_domain(model)

    async def get(self, signal_id: UUID) -> Signal | None:
        stmt = self._select_scoped(SignalModel).where(SignalModel.id == signal_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return signal_to_domain(model) if model is not None else None

    async def list_all(self) -> list[Signal]:
        """Every signal in this organization — the trigger-performance analytics read model
        (Milestone 22) groups over this by `signal_type`."""
        stmt = self._select_scoped(SignalModel)
        models = (await self._session.execute(stmt)).scalars().all()
        return [signal_to_domain(model) for model in models]
