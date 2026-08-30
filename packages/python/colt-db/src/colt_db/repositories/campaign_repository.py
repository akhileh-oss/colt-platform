"""Tenant-scoped repository for `Campaign` (CLAUDE.md §10.9)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from colt_db.mappers import campaign_to_domain
from colt_db.models.campaign import CampaignModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import Campaign


class SqlAlchemyCampaignRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        name: str,
        status: str = "DRAFT",
        objective: str | None = None,
        icp_definition: dict[str, Any] | None = None,
        rules: dict[str, Any] | None = None,
        channels: list[str] | None = None,
        schedule: dict[str, Any] | None = None,
        limits: dict[str, Any] | None = None,
        approval_policy: dict[str, Any] | None = None,
    ) -> Campaign:
        model = CampaignModel(
            organization_id=self.organization_id,
            name=name,
            status=status,
            objective=objective,
            icp_definition=icp_definition or {},
            rules=rules or {},
            channels=channels or [],
            schedule=schedule or {},
            limits=limits or {},
            approval_policy=approval_policy or {},
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return campaign_to_domain(model)

    async def get(self, campaign_id: UUID) -> Campaign | None:
        stmt = self._select_scoped(CampaignModel).where(CampaignModel.id == campaign_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return campaign_to_domain(model) if model is not None else None
