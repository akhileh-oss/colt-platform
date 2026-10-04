"""`CreateCampaign` (CLAUDE.md §10.9, Milestone 14).

Always creates a campaign in `CampaignStatus.DRAFT` — the port's `add()` does not even accept a
caller-supplied status, so there is no way to create a campaign into any other state. Reaching
`ACTIVE` always goes through `ValidateCampaign`.
"""

from __future__ import annotations

from typing import Any

from colt_application.ports.campaign_repository import CampaignRepository
from colt_domain import Campaign


class CreateCampaign:
    def __init__(self, campaigns: CampaignRepository) -> None:
        self._campaigns = campaigns

    async def __call__(
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
    ) -> Campaign:
        return await self._campaigns.add(
            name=name,
            objective=objective,
            icp_definition=icp_definition,
            rules=rules,
            channels=channels,
            schedule=schedule,
            limits=limits,
            approval_policy=approval_policy,
        )
