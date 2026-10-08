"""`ResumeCampaign` (CLAUDE.md §10.9, §48, Milestone 14, Milestone 24).

Requires the campaign to specifically be `PAUSED`, not merely that `campaign_state.
can_transition` allows a move to `ACTIVE` — `DRAFT` also reaches `ACTIVE` in that table, but
only through `ValidateCampaign`, which re-checks the campaign's definition. Resuming a `DRAFT`
campaign would activate it without ever running those checks.

Audited as a "campaign launch" the same way `ValidateCampaign`'s own first activation is
(CLAUDE.md §48): resuming a paused campaign puts it back into the same live-sending state a
launch does, and is just as much the kind of action §48 means by "campaign launch/pause."
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.errors import InvalidCampaignTransitionError, NotFoundError
from colt_application.ports.audit_log_repository import AuditLogRepository
from colt_application.ports.campaign_repository import CampaignRepository
from colt_domain import Campaign, CampaignStatus


class ResumeCampaign:
    def __init__(self, campaigns: CampaignRepository, audit_logs: AuditLogRepository) -> None:
        self._campaigns = campaigns
        self._audit_logs = audit_logs

    async def __call__(self, campaign_id: UUID, *, actor_id: UUID, now: datetime) -> Campaign:
        campaign = await self._campaigns.get(campaign_id)
        if campaign is None:
            raise NotFoundError(f"No campaign found with id {campaign_id}.")
        if campaign.status is not CampaignStatus.PAUSED:
            raise InvalidCampaignTransitionError(campaign.status.value, CampaignStatus.ACTIVE.value)
        updated = await self._campaigns.update_status(campaign_id, CampaignStatus.ACTIVE, at=now)
        await self._audit_logs.record(
            actor_type="user",
            actor_id=actor_id,
            action="campaign_resumed",
            entity_type="Campaign",
            entity_id=campaign_id,
        )
        return updated
