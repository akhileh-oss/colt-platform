"""`LeadOutreachWorkflow` against Temporal's in-process time-skipping test environment (CLAUDE.md
§45.4, §24.3, Milestone 18) — the same mechanism `test_example_workflow.py`/
`test_send_email_workflow.py` use.

Every activity touches real Postgres, the Anthropic API, or SMTP, so this test's `Worker`
registers fake callables under each real activity's wire name (`@activity.defn`'s default, the
function's own `__name__`) instead of the real ones. This proves the workflow's own
orchestration — eligibility gating, the research/draft/send sequence, the approval-wait poll
loop, the response-wait check, and sequence continuation — without any real I/O; the real-infra
proof that the underlying activities themselves work lives in each one's own integration test
(Milestones 10, 15, 16, 17).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from colt_workflows.activities.lead_outreach import (
    CheckConversationInput,
    CheckConversationOutput,
    DraftNextMessageInput,
    DraftNextMessageOutput,
    LoadOutreachStateInput,
    OutreachState,
    ResearchCompanyInput,
    ResearchCompanyOutput,
)
from colt_workflows.activities.send_email import SendEmailActivityInput, SendEmailActivityOutput
from colt_workflows.workflows.lead_outreach import LeadOutreachOutcome, LeadOutreachWorkflow

_Activity = Callable[[Any], Coroutine[Any, Any, Any]]

_TASK_QUEUE = "lead-outreach-workflow-test"


def _eligible_state(*, needs_research: bool = False, exhausted: bool = False) -> OutreachState:
    return OutreachState(
        eligible=True,
        ineligible_reason=None,
        needs_research=needs_research,
        company_id=str(uuid.uuid4()),
        company_name="Acme Rockets",
        company_domain="acme.example",
        person_id=str(uuid.uuid4()),
        person_name="Jane Doe",
        next_sequence_step_id=None if exhausted else str(uuid.uuid4()),
        next_sequence_step_channel=None if exhausted else "email",
        next_sequence_step_message_strategy=None if exhausted else "intro",
        next_sequence_step_delay_minutes=0 if exhausted else 1,
        sequence_exhausted=exhausted,
    )


async def _run(
    *,
    load_outreach_state_activity: _Activity,
    draft_next_message_activity: _Activity,
    send_email_activity: _Activity,
    check_conversation_activity: _Activity,
    research_company_activity: _Activity | None = None,
) -> LeadOutreachOutcome:
    activities: list[_Activity] = [
        load_outreach_state_activity,
        draft_next_message_activity,
        send_email_activity,
        check_conversation_activity,
    ]
    if research_company_activity is not None:
        activities.append(research_company_activity)

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[LeadOutreachWorkflow],
            activities=activities,
        ),
    ):
        return await env.client.execute_workflow(
            LeadOutreachWorkflow.run,
            args=[str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())],
            id=f"lead-outreach-{uuid.uuid4()}",
            task_queue=_TASK_QUEUE,
        )


@pytest.mark.asyncio
async def test_stops_immediately_for_an_ineligible_lead() -> None:
    @activity.defn(name="load_outreach_state_activity")
    async def load_outreach_state_activity(input: LoadOutreachStateInput) -> OutreachState:
        return OutreachState(
            eligible=False,
            ineligible_reason="suppressed",
            needs_research=False,
            company_id="",
            company_name="",
            company_domain="",
            person_id="",
            person_name="",
            next_sequence_step_id=None,
            next_sequence_step_channel=None,
            next_sequence_step_message_strategy=None,
            next_sequence_step_delay_minutes=0,
            sequence_exhausted=True,
        )

    @activity.defn(name="draft_next_message_activity")
    async def draft_next_message_activity(input: DraftNextMessageInput) -> DraftNextMessageOutput:
        raise AssertionError("must not draft for an ineligible lead")

    @activity.defn(name="send_email_activity")
    async def send_email_activity(input: SendEmailActivityInput) -> SendEmailActivityOutput:
        raise AssertionError("must not send for an ineligible lead")

    @activity.defn(name="check_conversation_activity")
    async def check_conversation_activity(
        input: CheckConversationInput,
    ) -> CheckConversationOutput:
        raise AssertionError("must not check conversation for an ineligible lead")

    result = await _run(
        load_outreach_state_activity=load_outreach_state_activity,
        draft_next_message_activity=draft_next_message_activity,
        send_email_activity=send_email_activity,
        check_conversation_activity=check_conversation_activity,
    )

    assert result.status == "STOPPED"
    assert result.detail == "suppressed"


@pytest.mark.asyncio
async def test_researches_when_needed_then_drafts_sends_and_completes_the_sequence() -> None:
    calls = {"load": 0}

    @activity.defn(name="load_outreach_state_activity")
    async def load_outreach_state_activity(input: LoadOutreachStateInput) -> OutreachState:
        calls["load"] += 1
        if calls["load"] == 1:
            return _eligible_state(needs_research=True)
        return _eligible_state(exhausted=True)

    @activity.defn(name="research_company_activity")
    async def research_company_activity(input: ResearchCompanyInput) -> ResearchCompanyOutput:
        return ResearchCompanyOutput(claims_recorded=3)

    @activity.defn(name="draft_next_message_activity")
    async def draft_next_message_activity(input: DraftNextMessageInput) -> DraftNextMessageOutput:
        return DraftNextMessageOutput(message_id=str(uuid.uuid4()))

    @activity.defn(name="send_email_activity")
    async def send_email_activity(input: SendEmailActivityInput) -> SendEmailActivityOutput:
        return SendEmailActivityOutput(status="SENT", provider_message_id="<sent@colt.local>")

    @activity.defn(name="check_conversation_activity")
    async def check_conversation_activity(
        input: CheckConversationInput,
    ) -> CheckConversationOutput:
        return CheckConversationOutput(replied=False, unsubscribed=False)

    result = await _run(
        load_outreach_state_activity=load_outreach_state_activity,
        research_company_activity=research_company_activity,
        draft_next_message_activity=draft_next_message_activity,
        send_email_activity=send_email_activity,
        check_conversation_activity=check_conversation_activity,
    )

    assert result.status == "SEQUENCE_COMPLETE"
    assert calls["load"] == 2


@pytest.mark.asyncio
async def test_waits_for_approval_then_sends_once_it_is_granted() -> None:
    send_calls = {"count": 0}

    @activity.defn(name="load_outreach_state_activity")
    async def load_outreach_state_activity(input: LoadOutreachStateInput) -> OutreachState:
        return _eligible_state(exhausted=send_calls["count"] > 0)

    @activity.defn(name="draft_next_message_activity")
    async def draft_next_message_activity(input: DraftNextMessageInput) -> DraftNextMessageOutput:
        return DraftNextMessageOutput(message_id=str(uuid.uuid4()))

    @activity.defn(name="send_email_activity")
    async def send_email_activity(input: SendEmailActivityInput) -> SendEmailActivityOutput:
        send_calls["count"] += 1
        if send_calls["count"] == 1:
            from temporalio.exceptions import ApplicationError

            raise ApplicationError(
                "Outbound send denied by policy (REQUIRE_APPROVAL): approval_status",
                non_retryable=True,
            )
        return SendEmailActivityOutput(status="SENT", provider_message_id="<sent@colt.local>")

    @activity.defn(name="check_conversation_activity")
    async def check_conversation_activity(
        input: CheckConversationInput,
    ) -> CheckConversationOutput:
        return CheckConversationOutput(replied=False, unsubscribed=False)

    result = await _run(
        load_outreach_state_activity=load_outreach_state_activity,
        draft_next_message_activity=draft_next_message_activity,
        send_email_activity=send_email_activity,
        check_conversation_activity=check_conversation_activity,
    )

    assert result.status == "SEQUENCE_COMPLETE"
    assert send_calls["count"] == 2


@pytest.mark.asyncio
async def test_stops_when_policy_denies_for_a_non_approval_reason() -> None:
    @activity.defn(name="load_outreach_state_activity")
    async def load_outreach_state_activity(input: LoadOutreachStateInput) -> OutreachState:
        return _eligible_state()

    @activity.defn(name="draft_next_message_activity")
    async def draft_next_message_activity(input: DraftNextMessageInput) -> DraftNextMessageOutput:
        return DraftNextMessageOutput(message_id=str(uuid.uuid4()))

    @activity.defn(name="send_email_activity")
    async def send_email_activity(input: SendEmailActivityInput) -> SendEmailActivityOutput:
        from temporalio.exceptions import ApplicationError

        raise ApplicationError(
            "Outbound send denied by policy (DENY): is_suppressed", non_retryable=True
        )

    @activity.defn(name="check_conversation_activity")
    async def check_conversation_activity(
        input: CheckConversationInput,
    ) -> CheckConversationOutput:
        raise AssertionError("must not check conversation after a non-approval policy denial")

    result = await _run(
        load_outreach_state_activity=load_outreach_state_activity,
        draft_next_message_activity=draft_next_message_activity,
        send_email_activity=send_email_activity,
        check_conversation_activity=check_conversation_activity,
    )

    assert result.status == "POLICY_DENIED"
    assert "is_suppressed" in result.detail


@pytest.mark.asyncio
async def test_stops_the_sequence_when_the_lead_replies() -> None:
    @activity.defn(name="load_outreach_state_activity")
    async def load_outreach_state_activity(input: LoadOutreachStateInput) -> OutreachState:
        return _eligible_state()

    @activity.defn(name="draft_next_message_activity")
    async def draft_next_message_activity(input: DraftNextMessageInput) -> DraftNextMessageOutput:
        return DraftNextMessageOutput(message_id=str(uuid.uuid4()))

    @activity.defn(name="send_email_activity")
    async def send_email_activity(input: SendEmailActivityInput) -> SendEmailActivityOutput:
        return SendEmailActivityOutput(status="SENT", provider_message_id="<sent@colt.local>")

    @activity.defn(name="check_conversation_activity")
    async def check_conversation_activity(
        input: CheckConversationInput,
    ) -> CheckConversationOutput:
        return CheckConversationOutput(replied=True, unsubscribed=False)

    result = await _run(
        load_outreach_state_activity=load_outreach_state_activity,
        draft_next_message_activity=draft_next_message_activity,
        send_email_activity=send_email_activity,
        check_conversation_activity=check_conversation_activity,
    )

    assert result.status == "REPLIED"


@pytest.mark.asyncio
async def test_stops_the_sequence_when_the_lead_unsubscribes() -> None:
    @activity.defn(name="load_outreach_state_activity")
    async def load_outreach_state_activity(input: LoadOutreachStateInput) -> OutreachState:
        return _eligible_state()

    @activity.defn(name="draft_next_message_activity")
    async def draft_next_message_activity(input: DraftNextMessageInput) -> DraftNextMessageOutput:
        return DraftNextMessageOutput(message_id=str(uuid.uuid4()))

    @activity.defn(name="send_email_activity")
    async def send_email_activity(input: SendEmailActivityInput) -> SendEmailActivityOutput:
        return SendEmailActivityOutput(status="SENT", provider_message_id="<sent@colt.local>")

    @activity.defn(name="check_conversation_activity")
    async def check_conversation_activity(
        input: CheckConversationInput,
    ) -> CheckConversationOutput:
        return CheckConversationOutput(replied=False, unsubscribed=True)

    result = await _run(
        load_outreach_state_activity=load_outreach_state_activity,
        draft_next_message_activity=draft_next_message_activity,
        send_email_activity=send_email_activity,
        check_conversation_activity=check_conversation_activity,
    )

    assert result.status == "UNSUBSCRIBED"
