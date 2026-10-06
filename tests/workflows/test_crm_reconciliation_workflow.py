"""`CrmReconciliationWorkflow` against Temporal's in-process time-skipping test environment
(CLAUDE.md §45.4, Milestone 20) — the same mechanism `test_send_email_workflow.py` uses.

`sync_entity_to_crm_activity` touches real Postgres and the configured `CRMProvider`, so this
test's `Worker` registers fake callables under the real activity's wire name
(`sync_entity_to_crm_activity`) instead of the real one. This proves the workflow's own
orchestration — running every target through the activity, collecting each outcome, and never
letting one target's exhausted retries abort the rest of the batch — without any real I/O; the
real-infra proof that CRM sync is idempotent and survives a simulated outage lives in
`tests/integration`'s Milestone 20 acceptance test.
"""

from __future__ import annotations

import uuid

import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from colt_workflows.activities.crm_sync import (
    SyncEntityToCrmActivityInput,
    SyncEntityToCrmActivityOutput,
)
from colt_workflows.workflows.crm_reconciliation import CrmReconciliationWorkflow, CrmSyncTarget

_TASK_QUEUE = "crm-reconciliation-workflow-test"


@activity.defn(name="sync_entity_to_crm_activity")
async def _fake_sync_always_succeeds(
    input: SyncEntityToCrmActivityInput,
) -> SyncEntityToCrmActivityOutput:
    return SyncEntityToCrmActivityOutput(
        sync_status="SYNCED",
        provider_object_id=f"fake-object-{input.entity_id}",
        last_error=None,
    )


@activity.defn(name="sync_entity_to_crm_activity")
async def _fake_sync_fails_for_one_target(
    input: SyncEntityToCrmActivityInput,
) -> SyncEntityToCrmActivityOutput:
    if input.entity_id == "broken":
        raise ApplicationError("simulated permanent provider rejection", non_retryable=True)
    return SyncEntityToCrmActivityOutput(
        sync_status="SYNCED", provider_object_id=f"fake-object-{input.entity_id}", last_error=None
    )


@pytest.mark.asyncio
async def test_every_target_in_the_batch_is_synced_and_returned() -> None:
    org_id = str(uuid.uuid4())
    targets = [
        CrmSyncTarget(entity_type="Company", entity_id="co-1", provider_account_id="acct-1"),
        CrmSyncTarget(entity_type="Person", entity_id="person-1", provider_account_id="acct-1"),
    ]

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[CrmReconciliationWorkflow],
            activities=[_fake_sync_always_succeeds],
        ),
    ):
        outcomes = await env.client.execute_workflow(
            CrmReconciliationWorkflow.run,
            args=[org_id, targets],
            id=f"crm-reconciliation-{uuid.uuid4()}",
            task_queue=_TASK_QUEUE,
        )

    assert len(outcomes) == 2
    assert {o.entity_id for o in outcomes} == {"co-1", "person-1"}
    assert all(o.sync_status == "SYNCED" for o in outcomes)


@pytest.mark.asyncio
async def test_one_targets_exhausted_retries_does_not_abort_the_rest_of_the_batch() -> None:
    org_id = str(uuid.uuid4())
    targets = [
        CrmSyncTarget(entity_type="Company", entity_id="broken", provider_account_id="acct-1"),
        CrmSyncTarget(entity_type="Company", entity_id="co-2", provider_account_id="acct-1"),
    ]

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[CrmReconciliationWorkflow],
            activities=[_fake_sync_fails_for_one_target],
        ),
    ):
        outcomes = await env.client.execute_workflow(
            CrmReconciliationWorkflow.run,
            args=[org_id, targets],
            id=f"crm-reconciliation-{uuid.uuid4()}",
            task_queue=_TASK_QUEUE,
        )

    by_entity = {o.entity_id: o for o in outcomes}
    assert by_entity["broken"].sync_status == "FAILED"
    assert by_entity["co-2"].sync_status == "SYNCED"
