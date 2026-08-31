"""`TraceCheckWorkflow` — proves CLAUDE.md §68's Milestone 07 acceptance criterion: a trace
spanning API → workflow → activity → DB.

Not a product workflow. Started only by the observability-verification endpoint
(`POST /api/v1/observability/trace-check` in `colt-api`), which exists for the same reason.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# See colt_workflows.workflows.example for why this import must be passed through: the
# activities package transitively imports colt_observability and colt_db, real I/O-capable
# libraries the workflow sandbox does not allow a workflow file to import directly.
with workflow.unsafe.imports_passed_through():
    from colt_workflows.activities.example import ExampleActivityInput, greet
    from colt_workflows.activities.trace_check import count_organizations


@workflow.defn
class TraceCheckWorkflow:
    @workflow.run
    async def run(self, name: str) -> dict[str, str | int]:
        greeting = await workflow.execute_activity(
            greet,
            ExampleActivityInput(name=name),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=1)),
        )
        organization_count = await workflow.execute_activity(
            count_organizations,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=1)),
        )
        return {"greeting": greeting, "organization_count": organization_count}
