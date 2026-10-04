"""Tenant-scoped repository for `SequenceStep` (CLAUDE.md §10.10)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from colt_db.mappers import sequence_step_to_domain
from colt_db.models.sequence_step import SequenceStepModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import SequenceStep


class SqlAlchemySequenceStepRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        campaign_id: UUID,
        step_order: int,
        channel: str,
        message_strategy: str,
        delay_after_previous: int = 0,
        conditions: dict[str, Any] | None = None,
        active: bool = True,
    ) -> SequenceStep:
        model = SequenceStepModel(
            organization_id=self.organization_id,
            campaign_id=campaign_id,
            step_order=step_order,
            channel=channel,
            delay_after_previous=delay_after_previous,
            message_strategy=message_strategy,
            conditions=conditions or {},
            active=active,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return sequence_step_to_domain(model)

    async def get(self, sequence_step_id: UUID) -> SequenceStep | None:
        stmt = self._select_scoped(SequenceStepModel).where(
            SequenceStepModel.id == sequence_step_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return sequence_step_to_domain(model) if model is not None else None

    async def list_by_campaign(self, campaign_id: UUID) -> list[SequenceStep]:
        stmt = (
            self._select_scoped(SequenceStepModel)
            .where(SequenceStepModel.campaign_id == campaign_id)
            .order_by(SequenceStepModel.step_order)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [sequence_step_to_domain(model) for model in models]
