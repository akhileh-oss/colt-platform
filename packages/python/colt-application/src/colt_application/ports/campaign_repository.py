"""The Campaign repository port.

Tenant-scoped, like `LeadRepository`: an implementation is bound to one `organization_id` at
construction and cannot be asked for (or to list) campaigns outside it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from colt_domain import Campaign, CampaignStatus


class CampaignRepository(Protocol):
    async def add(
        self,
        *,
        name: str,
        objective: str | None = None,
        icp_definition: dict[str, Any] | None = None,
        rules: dict[str, Any] | None = None,
        channels: list[str] | None = None,
        schedule: dict[str, Any] | None = None,
        limits: dict[str, Any] | None = None,
        approval_policy: dict[str, Any] | None = None,
    ) -> Campaign: ...

    async def get(self, campaign_id: UUID) -> Campaign | None: ...

    async def list_all(self) -> list[Campaign]: ...

    async def update_status(
        self, campaign_id: UUID, status: CampaignStatus, *, at: datetime
    ) -> Campaign: ...
