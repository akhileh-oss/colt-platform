"""`ValidateCampaign` (CLAUDE.md §10.9, §48, Milestone 14, Milestone 24) — the "validated" step
of Milestone 14's acceptance criterion, and the literal "campaign launch" CLAUDE.md §48 names
as an audited action — this codebase has no separately-named "launch" use case; a `DRAFT`
campaign's validation *is* its launch, the only way a campaign ever reaches `ACTIVE` for the
first time.

Only a `DRAFT` campaign can be validated (`InvalidCampaignTransitionError` otherwise). This is
deliberately a stricter check than `campaign_state.can_transition(status, ACTIVE)` alone would
give: `PAUSED` can also reach `ACTIVE`, but only via `ResumeCampaign` — validation re-running
the definition checks against an already-launched, merely-paused campaign would be meaningless,
and would let this use case resurrect it through a different door than `resume`. A `DRAFT`
campaign whose definition fails `campaign_state.validate_campaign_definition` stays `DRAFT` and
raises `CampaignValidationError` listing every failing rule; one that passes transitions to
`ACTIVE` and is audited — the same `audit_logs.record` call `DecideMessageApproval`/
`SendMessage`/`AddSuppressionEntry` already make for their own §48-named actions.
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
from colt_application.ports.audit_log_repository import AuditLogRepository
from colt_application.ports.campaign_repository import CampaignRepository
from colt_domain import Campaign, CampaignStatus


class ValidateCampaign:
    def __init__(self, campaigns: CampaignRepository, audit_logs: AuditLogRepository) -> None:
        self._campaigns = campaigns
        self._audit_logs = audit_logs

    async def __call__(self, campaign_id: UUID, *, actor_id: UUID, now: datetime) -> Campaign:
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

        updated = await self._campaigns.update_status(campaign_id, CampaignStatus.ACTIVE, at=now)
        await self._audit_logs.record(
            actor_type="user",
            actor_id=actor_id,
            action="campaign_launched",
            entity_type="Campaign",
            entity_id=campaign_id,
        )
        return updated
