"""`SendMessage` (CLAUDE.md §17, §17.1, §18, Milestone 16) — the one use case allowed to call
`MessageSender.send`, and only after `colt_policy.evaluate_outbound_send` returns `ALLOW`.

This is the literal mechanism behind Milestone 16's acceptance criterion: "a policy violation
cannot result in an external message send." `PolicyDeniedError` is raised *instead of* calling
the sender — never after — so a test can assert the sender was never invoked on any denied path.

Twelve of §17.1's fifteen checks are modeled (see `colt_policy.outbound` for which three are
deliberately deferred and why). `auto_approval_enabled` is a plain boolean, not a config read:
`colt_application` cannot depend on `colt_config` (§5's layering), so whether the
`ENABLE_AUTO_APPROVAL` feature flag (§51) is on is the caller's (the API layer's) job to resolve
and pass in as data, the same way every other use case here takes plain scalar arguments rather
than a provider-adapter or settings object directly.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from colt_application.errors import NotFoundError, PolicyDeniedError
from colt_application.ports.approval_repository import ApprovalRepository
from colt_application.ports.audit_log_repository import AuditLogRepository
from colt_application.ports.campaign_repository import CampaignRepository
from colt_application.ports.evidence_repository import EvidenceRepository
from colt_application.ports.lead_repository import LeadRepository
from colt_application.ports.message_repository import MessageRepository
from colt_application.ports.message_sender import MessageSender
from colt_application.ports.person_repository import PersonRepository
from colt_application.ports.suppression_repository import SuppressionRepository
from colt_domain import ApprovalStatus, EmailStatus, LeadStatus, Message, Person
from colt_policy import OutboundSendContext, PolicyDecision, evaluate_outbound_send

#: §17.1 check 8 names "daily/hourly rate limits" without specifying the exact window. A
#: trailing 24-hour window, not a campaign-timezone calendar day, is this milestone's own
#: documented choice — it needs no timezone to evaluate and "at most N per rolling day" is a
#: reasonable, defensible reading of "daily."
_RATE_LIMIT_WINDOW = timedelta(hours=24)


class SendMessage:
    def __init__(
        self,
        messages: MessageRepository,
        campaigns: CampaignRepository,
        leads: LeadRepository,
        persons: PersonRepository,
        evidence: EvidenceRepository,
        suppressions: SuppressionRepository,
        approvals: ApprovalRepository,
        sender: MessageSender,
        audit_logs: AuditLogRepository,
    ) -> None:
        self._messages = messages
        self._campaigns = campaigns
        self._leads = leads
        self._persons = persons
        self._evidence = evidence
        self._suppressions = suppressions
        self._approvals = approvals
        self._sender = sender
        self._audit_logs = audit_logs

    async def __call__(
        self, message_id: UUID, *, now: datetime, auto_approval_enabled: bool
    ) -> Message:
        message = await self._messages.get(message_id)
        if message is None:
            raise NotFoundError(f"No message found with id {message_id}.")
        campaign = await self._campaigns.get(message.campaign_id)
        if campaign is None:
            raise NotFoundError(f"No campaign found with id {message.campaign_id}.")
        lead = await self._leads.get(message.lead_id)
        if lead is None:
            raise NotFoundError(f"No lead found with id {message.lead_id}.")
        person = await self._persons.get(lead.person_id)
        if person is None:
            raise NotFoundError(f"No person found with id {lead.person_id}.")

        is_suppressed = (
            await self._suppressions.is_suppressed("email", person.email)
            if message.channel == "email" and person.email
            else False
        )

        max_per_day = campaign.limits.get("max_sends_per_day")
        rate_limit_ok = (
            True
            if max_per_day is None
            else await self._messages.count_sent_since(campaign.id, now - _RATE_LIMIT_WINDOW)
            < max_per_day
        )

        evidence_valid = True
        for evidence_id in message.evidence_ids:
            if await self._evidence.get(evidence_id) is None:
                evidence_valid = False
                break

        auto_approve_allowed = (
            auto_approval_enabled and campaign.approval_policy.get("mode") == "auto"
        )
        approval_required = not auto_approve_allowed
        approval = await self._approvals.get_latest_for_entity("Message", message_id)
        approval_status = approval.status if approval is not None else ApprovalStatus.PENDING

        context = OutboundSendContext(
            lead_belongs_to_organization=lead.organization_id == campaign.organization_id,
            target_identity_valid=_target_identity_valid(message.channel, person),
            is_suppressed=is_suppressed,
            channel_allowed=message.channel in campaign.channels,
            campaign_active=campaign.status.value == "ACTIVE",
            rate_limit_ok=rate_limit_ok,
            message_matches_target=message.lead_id == lead.id
            and message.campaign_id == campaign.id,
            evidence_valid=evidence_valid,
            no_duplicate_send=message.status != "SENT",
            approval_required=approval_required,
            approval_status=approval_status,
            send_window_ok=True,
        )
        evaluation = evaluate_outbound_send(context)
        if evaluation.decision != PolicyDecision.ALLOW:
            raise PolicyDeniedError(evaluation.decision.value, evaluation.failed_checks)

        provider_message_id = await self._sender.send(message)
        updated = await self._messages.update_send_result(
            message_id, status="SENT", sent_at=now, provider_message_id=provider_message_id
        )
        if lead.status == LeadStatus.READY:
            await self._leads.update_status(lead.id, LeadStatus.CONTACTED, at=now)

        await self._audit_logs.record(
            actor_type="system",
            action="message_sent",
            entity_type="Message",
            entity_id=message_id,
            metadata={
                "campaign_id": str(campaign.id),
                "lead_id": str(lead.id),
                "provider_message_id": provider_message_id,
            },
        )
        return updated


def _target_identity_valid(channel: str, person: Person) -> bool:
    """§17.1 check 3. Documented, channel-specific: an email send needs a non-blank email not
    already known to be bad; every other channel needs a LinkedIn URL — the only two identifiers
    `Person` (§10.4) carries today."""
    if channel == "email":
        return bool(person.email) and person.email_status != EmailStatus.INVALID
    return bool(person.linkedin_url)
