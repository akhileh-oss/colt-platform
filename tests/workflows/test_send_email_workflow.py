"""`SendEmailWorkflow` against Temporal's in-process time-skipping test environment (CLAUDE.md
§45.4, Milestone 17) — the same mechanism `test_example_workflow.py` uses.

`send_email_activity` touches real Postgres and SMTP, so this test's `Worker` registers a fake
callable under the real activity's wire name (`@activity.defn`'s default, the function's own
`__name__` — "send_email_activity") instead of the real one. This proves the workflow's own
orchestration (passing input through, returning the activity's result, propagating a
non-retryable failure) without any real I/O; the real-infra proof that this workflow actually
sends mail through Mailpit lives in `tests/integration`'s Milestone 17 acceptance test.
"""

from __future__ import annotations

import uuid

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ActivityError, ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from colt_workflows.activities.send_email import SendEmailActivityInput, SendEmailActivityOutput
from colt_workflows.workflows.send_email import SendEmailWorkflow

_TASK_QUEUE = "send-email-workflow-test"


@activity.defn(name="send_email_activity")
async def _fake_send_email_activity(input: SendEmailActivityInput) -> SendEmailActivityOutput:
    return SendEmailActivityOutput(status="SENT", provider_message_id="<fake-send@colt.local>")


@activity.defn(name="send_email_activity")
async def _fake_send_email_activity_denied(
    input: SendEmailActivityInput,
) -> SendEmailActivityOutput:
    raise ApplicationError(
        "Outbound send denied by policy (DENY): is_suppressed", non_retryable=True
    )


@pytest.mark.asyncio
async def test_send_email_workflow_returns_the_activitys_result() -> None:
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[SendEmailWorkflow],
            activities=[_fake_send_email_activity],
        ),
    ):
        result = await env.client.execute_workflow(
            SendEmailWorkflow.run,
            args=[str(uuid.uuid4()), str(uuid.uuid4())],
            id=f"send-email-workflow-{uuid.uuid4()}",
            task_queue=_TASK_QUEUE,
        )

    assert result.status == "SENT"
    assert result.provider_message_id == "<fake-send@colt.local>"


@pytest.mark.asyncio
async def test_send_email_workflow_propagates_a_non_retryable_policy_denial() -> None:
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[SendEmailWorkflow],
            activities=[_fake_send_email_activity_denied],
        ),
    ):
        with pytest.raises(WorkflowFailureError) as exc_info:
            await env.client.execute_workflow(
                SendEmailWorkflow.run,
                args=[str(uuid.uuid4()), str(uuid.uuid4())],
                id=f"send-email-workflow-{uuid.uuid4()}",
                task_queue=_TASK_QUEUE,
            )

    activity_error = exc_info.value.cause
    assert isinstance(activity_error, ActivityError)
    application_error = activity_error.cause
    assert isinstance(application_error, ApplicationError)
    assert application_error.non_retryable
