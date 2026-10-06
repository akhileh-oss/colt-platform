"""`LeadOutreachWorkflow` (CLAUDE.md §24.3, Milestone 18) — the durable orchestration of one
lead through one campaign's sequence: research check, personalization, message generation,
policy check, approval wait, send, response wait, sequence continuation.

This is not a signal-driven design: rather than wiring every REST route that could change a
message's approval or a lead's conversation state to also push a Temporal signal into a running
workflow, this workflow polls its own durable state (via `workflow.sleep` between activity
calls) for both the approval-wait and response-wait steps. That state is the same Postgres rows
`DecideMessageApproval` (Milestone 16) and `ProcessInboundEmail`/`UnsubscribeByToken` (Milestone
17) already write — polling them is simpler and no less correct than a signal-correlation layer
across those existing, already-shipped REST routes, and `workflow.sleep` between polls is still
fully durable (the acceptance criterion's "survives restarts").

Reuses `send_email_activity` (Milestone 17) for the actual send rather than reimplementing
`SendMessage`'s policy-gated path a second time — composition, not duplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

# See colt_workflows.workflows.example for why this import must be passed through: the
# activities package transitively imports colt_db/colt_application/colt_agents/colt_integrations,
# real I/O-capable libraries the workflow sandbox does not allow a workflow file to import
# directly.
with workflow.unsafe.imports_passed_through():
    from colt_workflows.activities.lead_outreach import (
        CheckConversationInput,
        CheckConversationOutput,
        DraftNextMessageInput,
        LoadOutreachStateInput,
        OutreachState,
        ResearchCompanyInput,
        check_conversation_activity,
        draft_next_message_activity,
        load_outreach_state_activity,
        research_company_activity,
    )
    from colt_workflows.activities.reply_intelligence import (
        ClassifyReplyActivityInput,
        classify_reply_activity,
    )
    from colt_workflows.activities.send_email import SendEmailActivityInput, send_email_activity

#: How often to poll while waiting on a human approval decision, and the longest this workflow
#: will wait before giving up on one run of this sequence step (CLAUDE.md names no SLA for a
#: human decision — a bounded wait that eventually ends the workflow run, rather than an
#: unbounded one, is this milestone's own documented choice).
_APPROVAL_POLL_INTERVAL = timedelta(minutes=5)
_APPROVAL_MAX_WAIT = timedelta(hours=48)

_DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=5, initial_interval=timedelta(seconds=2))


@dataclass(frozen=True)
class LeadOutreachOutcome:
    status: str
    detail: str


@workflow.defn
class LeadOutreachWorkflow:
    @workflow.run
    async def run(
        self,
        organization_id: str,
        lead_id: str,
        campaign_id: str,
        *,
        auto_approval_enabled: bool = False,
    ) -> LeadOutreachOutcome:
        while True:
            state = await workflow.execute_activity(
                load_outreach_state_activity,
                LoadOutreachStateInput(
                    organization_id=organization_id, lead_id=lead_id, campaign_id=campaign_id
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            assert isinstance(state, OutreachState)  # noqa: S101 - the activity's own return
            # type annotation already guarantees this; narrows it for the type checker.

            if not state.eligible:
                return LeadOutreachOutcome(status="STOPPED", detail=state.ineligible_reason or "")
            if state.sequence_exhausted:
                return LeadOutreachOutcome(status="SEQUENCE_COMPLETE", detail="")

            if state.needs_research:
                await workflow.execute_activity(
                    research_company_activity,
                    ResearchCompanyInput(
                        organization_id=organization_id,
                        company_id=state.company_id,
                        company_name=state.company_name,
                        company_domain=state.company_domain,
                    ),
                    start_to_close_timeout=timedelta(seconds=300),
                    retry_policy=_DEFAULT_RETRY_POLICY,
                )

            assert state.next_sequence_step_id is not None  # noqa: S101 - guaranteed by
            # `sequence_exhausted` being False, already checked above.
            draft = await workflow.execute_activity(
                draft_next_message_activity,
                DraftNextMessageInput(
                    organization_id=organization_id,
                    lead_id=lead_id,
                    campaign_id=campaign_id,
                    sequence_step_id=state.next_sequence_step_id,
                    channel=state.next_sequence_step_channel or "email",
                    message_strategy=state.next_sequence_step_message_strategy or "",
                    company_name=state.company_name,
                    person_name=state.person_name,
                ),
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )

            send_outcome = await self._send_with_approval_wait(
                organization_id, draft.message_id, auto_approval_enabled
            )
            if send_outcome is not None:
                return send_outcome

            sent_at = workflow.now()
            wait_minutes = max(state.next_sequence_step_delay_minutes, 1)
            await workflow.sleep(timedelta(minutes=wait_minutes))

            conversation = await workflow.execute_activity(
                check_conversation_activity,
                CheckConversationInput(
                    organization_id=organization_id,
                    lead_id=lead_id,
                    since=sent_at.isoformat(),
                ),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
            assert isinstance(conversation, CheckConversationOutput)  # noqa: S101 - same
            # narrowing as `state` above.
            if conversation.unsubscribed:
                return LeadOutreachOutcome(status="UNSUBSCRIBED", detail="")
            if conversation.replied:
                # "If a reply is received: terminate automated sequence; classify reply"
                # (CLAUDE.md §23.1) — ReplyIntelligenceAgent (§12.10, Milestone 19) does the
                # classification; this workflow's own job ends at terminating the sequence.
                if conversation.conversation_id is not None:
                    await workflow.execute_activity(
                        classify_reply_activity,
                        ClassifyReplyActivityInput(
                            organization_id=organization_id,
                            conversation_id=conversation.conversation_id,
                        ),
                        start_to_close_timeout=timedelta(seconds=120),
                        retry_policy=_DEFAULT_RETRY_POLICY,
                    )
                return LeadOutreachOutcome(status="REPLIED", detail="")

            # Neither — sequence continuation: loop back and re-evaluate state for the next step.

    async def _send_with_approval_wait(
        self, organization_id: str, message_id: str, auto_approval_enabled: bool
    ) -> LeadOutreachOutcome | None:
        """Attempt the send; if policy denies it only because a human approval decision is
        pending, poll for that decision rather than failing the workflow run. Returns an
        outcome if the workflow should stop here, or `None` to continue to the response-wait
        step after a successful send."""
        waited = timedelta()
        while True:
            try:
                await workflow.execute_activity(
                    send_email_activity,
                    SendEmailActivityInput(
                        organization_id=organization_id,
                        message_id=message_id,
                        auto_approval_enabled=auto_approval_enabled,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=_DEFAULT_RETRY_POLICY,
                )
                return None
            except ActivityError as exc:
                cause = exc.cause
                if not isinstance(cause, ApplicationError):
                    raise
                if "REQUIRE_APPROVAL" not in cause.message:
                    return LeadOutreachOutcome(status="POLICY_DENIED", detail=cause.message)

            if waited >= _APPROVAL_MAX_WAIT:
                return LeadOutreachOutcome(status="APPROVAL_TIMED_OUT", detail=message_id)
            await workflow.sleep(_APPROVAL_POLL_INTERVAL)
            waited += _APPROVAL_POLL_INTERVAL
