"""`ExampleWorkflow` — Milestone 06's foundation workflow: durable, restart-survives, nothing
more.

Not a real product workflow (`LeadOutreachWorkflow`, §24.3, lands in Milestone 18). Its one job
is to prove the worker harness — activity execution with retries, and a timer that survives a
worker restart — works against a real Temporal server, per this milestone's acceptance
criterion.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# The activities package's __init__ transitively imports colt_observability (OpenTelemetry,
# Milestone 07) and colt_db (SQLAlchemy/asyncpg) — real I/O-capable libraries the workflow
# sandbox will not let a workflow file import directly, since a workflow must be deterministic
# and never touch either at runtime itself (only inside an activity, which does run outside the
# sandbox). `imports_passed_through` tells the sandbox this import is trusted infrastructure,
# not workflow logic to validate.
with workflow.unsafe.imports_passed_through():
    from colt_workflows.activities.example import ExampleActivityInput, greet


@workflow.defn
class ExampleWorkflow:
    @workflow.run
    async def run(self, name: str, *, wait_seconds: int = 5) -> str:
        greeting = await workflow.execute_activity(
            greet,
            ExampleActivityInput(name=name),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=1)),
        )
        # Tracked by the Temporal server, not by worker process memory — a worker that dies
        # mid-sleep and is replaced by a fresh one still resumes here, at the correct remaining
        # duration, once the replacement polls the task queue. This is the durability the
        # milestone's acceptance criterion (a workflow that survives a worker restart) tests.
        await workflow.sleep(timedelta(seconds=wait_seconds))
        return greeting
