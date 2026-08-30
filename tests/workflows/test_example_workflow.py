"""`ExampleWorkflow` against Temporal's in-process time-skipping test environment (CLAUDE.md
§45.4).

No real Temporal server or worker process — `WorkflowEnvironment.start_time_skipping()` runs an
ephemeral in-memory server with virtual time, so the workflow's `workflow.sleep()` resolves
instantly rather than the suite actually waiting out the real duration. This proves the
workflow's *logic* (activity call, retry policy, timer, return value); the real-server proof
that a worker restart doesn't lose progress lives in
`tests/integration/test_workflow_durability.py`, which this environment cannot substitute for —
there is no worker process here to restart.
"""

from __future__ import annotations

import uuid

import pytest
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ActivityError, ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from colt_workflows.activities.example import greet
from colt_workflows.workflows.example import ExampleWorkflow


@pytest.mark.asyncio
async def test_example_workflow_returns_a_greeting() -> None:
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="example-workflow-test",
            workflows=[ExampleWorkflow],
            activities=[greet],
        ),
    ):
        result = await env.client.execute_workflow(
            ExampleWorkflow.run,
            "Ada",
            id=f"example-workflow-{uuid.uuid4()}",
            task_queue="example-workflow-test",
        )

    assert result == "Hello, Ada!"


@pytest.mark.asyncio
async def test_example_workflow_propagates_a_non_retryable_activity_failure() -> None:
    """A blank name is never valid, on any retry — the workflow must fail, not hang retrying."""
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="example-workflow-test",
            workflows=[ExampleWorkflow],
            activities=[greet],
        ),
    ):
        with pytest.raises(WorkflowFailureError) as exc_info:
            await env.client.execute_workflow(
                ExampleWorkflow.run,
                "   ",
                id=f"example-workflow-{uuid.uuid4()}",
                task_queue="example-workflow-test",
            )

    activity_error = exc_info.value.cause
    assert isinstance(activity_error, ActivityError)
    application_error = activity_error.cause
    assert isinstance(application_error, ApplicationError)
    assert application_error.non_retryable
