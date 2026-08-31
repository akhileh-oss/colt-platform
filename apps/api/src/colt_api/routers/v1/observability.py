"""Observability verification (CLAUDE.md §68, Milestone 07).

`POST /observability/trace-check` is not a product endpoint — it starts `TraceCheckWorkflow`
purely to give Milestone 07's acceptance criterion something to prove against a real request:
one trace spanning the API request, the workflow, its activities, and a real database query.
`LeadOutreachWorkflow` (§24.3) is the first *product* workflow the API starts, in Milestone 18.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from colt_api.dependencies import PrincipalDep, SettingsDep, TemporalClientDep
from colt_observability import get_log_context
from colt_workflows.workflows.trace_check import TraceCheckWorkflow

router = APIRouter(prefix="/observability", tags=["observability"])


class TraceCheckRequest(BaseModel):
    name: str = "Colt"


class TraceCheckResponse(BaseModel):
    workflow_id: str
    greeting: str
    organization_count: int
    #: The trace ID this request's own span was part of — not returned for client convenience,
    #: but so an automated test can assert the *same* ID shows up in the worker process's own
    #: activity logs, proving the trace actually propagated across the real Temporal RPC
    #: boundary rather than trusting the SDK's documentation for it.
    trace_id: str | None


@router.post("/trace-check", response_model=TraceCheckResponse)
async def trace_check(
    body: TraceCheckRequest,
    client: TemporalClientDep,
    settings: SettingsDep,
    _principal: PrincipalDep,
) -> TraceCheckResponse:
    """Start `TraceCheckWorkflow` and await its result.

    Requires authentication like every other route beyond the health probes — this still
    touches the database and starts real workflow executions, so it is not exempt from §27 just
    because its purpose is diagnostic.
    """
    workflow_id = f"trace-check-{uuid4()}"
    result = await client.execute_workflow(
        TraceCheckWorkflow.run,
        body.name,
        id=workflow_id,
        task_queue=settings.temporal.task_queue,
    )
    return TraceCheckResponse(
        workflow_id=workflow_id,
        greeting=str(result["greeting"]),
        organization_count=int(result["organization_count"]),
        trace_id=get_log_context().get("trace_id"),
    )
