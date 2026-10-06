"""`SendEmailWorkflow` (CLAUDE.md §24, §29, Milestone 17) — the durable send-queue/workflow
Build item: a `Message` enters this workflow's task queue and the workflow drives it through
`send_email_activity` with retries, surviving a worker restart the same way `ExampleWorkflow`
(Milestone 06) does.

Not `LeadOutreachWorkflow` (§24.3, Milestone 18's own, broader sequencing workflow) — this is
the one-message send leg a sequencing workflow will eventually call into, scoped to exactly what
Milestone 17's Build list asks for.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# See colt_workflows.workflows.example for why this import must be passed through: the
# activities package transitively imports colt_db/colt_application/colt_integrations, real
# I/O-capable libraries the workflow sandbox does not allow a workflow file to import directly.
with workflow.unsafe.imports_passed_through():
    from colt_workflows.activities.send_email import (
        SendEmailActivityInput,
        SendEmailActivityOutput,
        send_email_activity,
    )


@workflow.defn
class SendEmailWorkflow:
    @workflow.run
    async def run(
        self,
        organization_id: str,
        message_id: str,
        *,
        auto_approval_enabled: bool = False,
    ) -> SendEmailActivityOutput:
        return await workflow.execute_activity(
            send_email_activity,
            SendEmailActivityInput(
                organization_id=organization_id,
                message_id=message_id,
                auto_approval_enabled=auto_approval_enabled,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=5, initial_interval=timedelta(seconds=2)),
        )
