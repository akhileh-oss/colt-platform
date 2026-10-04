"""`ValidateCampaign` (CLAUDE.md §10.9, Milestone 14) — the "validated" step of this milestone's
acceptance criterion.

Only a `DRAFT` campaign can be validated (`InvalidCampaignTransitionError` otherwise). This is
deliberately a stricter check than `campaign_state.can_transition(status, ACTIVE)` alone would
give: `PAUSED` can also reach `ACTIVE`, but only via `ResumeCampaign` — validation re-running
the definition checks against an already-launched, merely-paused campaign would be meaningless,
and would let this use case resurrect it through a different door than `resume`. A `DRAFT`
campaign whose definition fails `campaign_state.validate_campaign_definition` stays `DRAFT` and
raises `CampaignValidationError` listing every failing rule; one that passes transitions to
`ACTIVE`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.campaign_state import validate_campaign_definition
from colt_application.errors import (
    CampaignValidationError,
    InvalidCampaignTransitionError,
    NotFoundError,
)
from colt_application.ports.campaign_repository import CampaignRepository
from colt_domain import Campaign, CampaignStatus


class ValidateCampaign:
    def __init__(self, campaigns: CampaignRepository) -> None:
        self._campaigns = campaigns

    async def __call__(self, campaign_id: UUID, *, now: datetime) -> Campaign:
        campaign = await self._campaigns.get(campaign_id)
        if campaign is None:
            raise NotFoundError(f"No campaign found with id {campaign_id}.")
        if campaign.status is not CampaignStatus.DRAFT:
            raise InvalidCampaignTransitionError(campaign.status.value, CampaignStatus.ACTIVE.value)

        issues = validate_campaign_definition(
            icp_definition=campaign.icp_definition,
            channels=campaign.channels,
            schedule=campaign.schedule,
            limits=campaign.limits,
        )
        if issues:
            raise CampaignValidationError(issues)

        return await self._campaigns.update_status(campaign_id, CampaignStatus.ACTIVE, at=now)
