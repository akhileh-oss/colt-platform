"""`DecideMessageApproval` (CLAUDE.md §10.17, §26.2 `MESSAGE_APPROVE`, Milestone 16).

A message is implicitly "requested for approval" the moment it is drafted (Milestone 15's
`DraftMessage` already starts every `Message` at `approval_status="PENDING"`) — CLAUDE.md names
no separate request step, so this use case lazily creates the `Approval` row representing that
standing request the first time a decision is made, rather than requiring some other code path
to have created it first.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.errors import InvalidApprovalTransitionError, NotFoundError
from colt_application.ports.approval_repository import ApprovalRepository
from colt_application.ports.audit_log_repository import AuditLogRepository
from colt_application.ports.lead_repository import LeadRepository
from colt_application.ports.message_repository import MessageRepository
from colt_domain import ApprovalStatus, LeadStatus, Message


class DecideMessageApproval:
    def __init__(
        self,
        messages: MessageRepository,
        approvals: ApprovalRepository,
        leads: LeadRepository,
        audit_logs: AuditLogRepository,
    ) -> None:
        self._messages = messages
        self._approvals = approvals
        self._leads = leads
        self._audit_logs = audit_logs

    async def __call__(
        self,
        message_id: UUID,
        *,
        approve: bool,
        decided_by: UUID,
        reason: str | None,
        now: datetime,
    ) -> Message:
        message = await self._messages.get(message_id)
        if message is None:
            raise NotFoundError(f"No message found with id {message_id}.")

        approval = await self._approvals.get_latest_for_entity("Message", message_id)
        if approval is None:
            approval = await self._approvals.add(
                entity_type="Message", entity_id=message_id, action_type="MESSAGE_SEND"
            )
        if approval.status != ApprovalStatus.PENDING:
            raise InvalidApprovalTransitionError(approval.status.value)

        decision = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
        await self._approvals.decide(
            approval.id, status=decision, approved_by=decided_by, reason=reason, decided_at=now
        )
        updated = await self._messages.update_approval_status(
            message_id, approval_status=decision.value
        )

        # Only an approval moves the lead forward — a rejection leaves its status untouched
        # (CLAUDE.md names no "rejected" lead state) for a human to act on through other means.
        if approve:
            lead = await self._leads.get(message.lead_id)
            if lead is not None and lead.status == LeadStatus.PENDING_APPROVAL:
                await self._leads.update_status(lead.id, LeadStatus.READY, at=now)

        await self._audit_logs.record(
            actor_type="user",
            actor_id=decided_by,
            action="message_approval_decided",
            entity_type="Message",
            entity_id=message_id,
            metadata={"decision": decision.value, "reason": reason},
        )
        return updated
