"""`CrmReconciliationWorkflow` (CLAUDE.md §30, Milestone 20) — the "reconciliation workflow"
Build item: durably re-drives a batch of entities through `sync_entity_to_crm_activity`,
regardless of whether any individual target is syncing for the first time or retrying after a
prior failure.

CLAUDE.md §30's acceptance criterion is "CRM outage does not break core Colt workflows; sync
retries safely after recovery." The second half is this workflow's job: Temporal's own
`RetryPolicy` re-runs a target whose activity attempt raised a retryable `ProviderError`
(§28.1 — rate limit, timeout, 5xx) automatically, and the activity's own idempotent upsert
(`RecordCrmSyncOutcome`, keyed by `(entity_type, entity_id, provider_name)`) means a later
successful retry updates the same `CrmSyncRecord` row rather than creating a second one — no
duplicate provider object is ever created by a retry. The first half (an outage never blocks
unrelated Colt work) is structural: nothing else in the codebase calls into this workflow or its
activity synchronously, so a CRM outage can only ever stall *this* workflow's own run, never a
caller.

One activity failure does not abort the whole batch: each target's outcome (success or final
failure, after `_DEFAULT_RETRY_POLICY` is exhausted) is collected and returned, so one
permanently-broken target does not prevent reconciling the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

# See colt_workflows.workflows.example for why this import must be passed through: the
# activities package transitively imports colt_db/colt_application/colt_integrations, real
# I/O-capable libraries the workflow sandbox does not allow a workflow file to import directly.
with workflow.unsafe.imports_passed_through():
    from colt_workflows.activities.crm_sync import (
        SyncEntityToCrmActivityInput,
        SyncEntityToCrmActivityOutput,
        sync_entity_to_crm_activity,
    )

_DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=5, initial_interval=timedelta(seconds=2))


@dataclass(frozen=True)
class CrmSyncTarget:
    entity_type: str  # "Company" | "Person" | "Opportunity" | "Task"
    entity_id: str
    provider_account_id: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CrmReconciliationOutcome:
    entity_type: str
    entity_id: str
    sync_status: str
    provider_object_id: str | None
    last_error: str | None


@workflow.defn
class CrmReconciliationWorkflow:
    @workflow.run
    async def run(
        self, organization_id: str, targets: list[CrmSyncTarget]
    ) -> list[CrmReconciliationOutcome]:
        outcomes: list[CrmReconciliationOutcome] = []
        for target in targets:
            try:
                result: SyncEntityToCrmActivityOutput = await workflow.execute_activity(
                    sync_entity_to_crm_activity,
                    SyncEntityToCrmActivityInput(
                        organization_id=organization_id,
                        entity_type=target.entity_type,
                        entity_id=target.entity_id,
                        provider_account_id=target.provider_account_id,
                        fields=target.fields,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=_DEFAULT_RETRY_POLICY,
                )
                outcomes.append(
                    CrmReconciliationOutcome(
                        entity_type=target.entity_type,
                        entity_id=target.entity_id,
                        sync_status=result.sync_status,
                        provider_object_id=result.provider_object_id,
                        last_error=result.last_error,
                    )
                )
            except ActivityError as exc:
                # Every retry attempt the policy allows is exhausted — this target stays FAILED
                # (the activity itself already recorded that via RecordCrmSyncOutcome before
                # raising), but one target's exhausted retries must not abort the rest of the
                # batch.
                outcomes.append(
                    CrmReconciliationOutcome(
                        entity_type=target.entity_type,
                        entity_id=target.entity_id,
                        sync_status="FAILED",
                        provider_object_id=None,
                        last_error=str(exc),
                    )
                )
        return outcomes
