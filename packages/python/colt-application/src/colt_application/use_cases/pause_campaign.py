"""`PauseCampaign` (CLAUDE.md §10.9, §48, Milestone 14, Milestone 24) — CLAUDE.md §48's
"campaign launch/pause" is this use case's own half of that pair, audited the same way
`DecideMessageApproval`/`SendMessage`/`AddSuppressionEntry` already audit their own §48-named
actions.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.campaign_state import can_transition
from colt_application.errors import InvalidCampaignTransitionError, NotFoundError
from colt_application.ports.audit_log_repository import AuditLogRepository
from colt_application.ports.campaign_repository import CampaignRepository
from colt_domain import Campaign, CampaignStatus


class PauseCampaign:
    def __init__(self, campaigns: CampaignRepository, audit_logs: AuditLogRepository) -> None:
        self._campaigns = campaigns
        self._audit_logs = audit_logs

    async def __call__(self, campaign_id: UUID, *, actor_id: UUID, now: datetime) -> Campaign:
        campaign = await self._campaigns.get(campaign_id)
        if campaign is None:
            raise NotFoundError(f"No campaign found with id {campaign_id}.")
        if not can_transition(campaign.status, CampaignStatus.PAUSED):
            raise InvalidCampaignTransitionError(campaign.status.value, CampaignStatus.PAUSED.value)
        updated = await self._campaigns.update_status(campaign_id, CampaignStatus.PAUSED, at=now)
        await self._audit_logs.record(
            actor_type="user",
            actor_id=actor_id,
            action="campaign_paused",
            entity_type="Campaign",
            entity_id=campaign_id,
        )
        return updated
