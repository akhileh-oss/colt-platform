"""The Temporal worker process (CLAUDE.md §3.3, §24, §35, §58).

`run_worker` is factored out from `__main__` so both the real process entry point and tests
(hermetic and real-infra alike) construct a worker the same way — the durability test in
`tests/integration` runs this exact function in a subprocess, not a test-only stand-in.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor
from temporalio.worker import Worker

from colt_config import Settings, get_settings
from colt_observability import configure_tracing, get_logger, instrument_sqlalchemy
from colt_workflows.activities.example import greet
from colt_workflows.activities.lead_outreach import (
    check_conversation_activity,
    draft_next_message_activity,
    load_outreach_state_activity,
    research_company_activity,
)
from colt_workflows.activities.send_email import send_email_activity
from colt_workflows.activities.trace_check import count_organizations
from colt_workflows.workflows.example import ExampleWorkflow
from colt_workflows.workflows.lead_outreach import LeadOutreachWorkflow
from colt_workflows.workflows.send_email import SendEmailWorkflow
from colt_workflows.workflows.trace_check import TraceCheckWorkflow

logger = get_logger(__name__)

#: Every workflow and activity this worker executes. Later milestones register their own here
#: as they add real workflows.
WORKFLOWS: Sequence[type] = (
    ExampleWorkflow,
    TraceCheckWorkflow,
    SendEmailWorkflow,
    LeadOutreachWorkflow,
)
ACTIVITIES: Sequence[Any] = (
    greet,
    count_organizations,
    send_email_activity,
    load_outreach_state_activity,
    research_company_activity,
    draft_next_message_activity,
    check_conversation_activity,
)


async def run_worker(
    settings: Settings | None = None, *, shutdown_event: asyncio.Event | None = None
) -> None:
    """Connect to Temporal and run the worker until `shutdown_event` is set.

    A caller-supplied event lets the durability test and `__main__`'s signal handlers stop a
    specific worker deterministically, awaiting the SDK's own graceful shutdown (`async with
    worker:` drains in-flight activity tasks on exit rather than dropping them, §58) instead of
    killing the process outright.
    """
    settings = settings or get_settings()
    shutdown_event = shutdown_event or asyncio.Event()

    # Without this, `TracingInterceptor` below still creates spans, but against OpenTelemetry's
    # default no-op provider — a span whose context is never valid, so `get_log_context()` would
    # never see a trace_id to correlate activity logs with, and nothing would export. This is
    # the worker's own tracer, distinct from the API process's (colt_api.app.create_app());
    # each process configures its own, exactly like each configures its own logging.
    configure_tracing(
        service_name=settings.observability.service_name,
        otlp_endpoint=settings.observability.otel_endpoint,
        sample_rate=settings.observability.trace_sample_rate,
    )
    # A DB span needs SQLAlchemy instrumented in *this* process too — `count_organizations`
    # opens its own engine here, in the worker, not in the API process that started the
    # workflow (CLAUDE.md §68: the trace must span API → workflow → activity → DB).
    instrument_sqlalchemy()

    client = await Client.connect(
        settings.temporal.address,
        namespace=settings.temporal.namespace,
        # Reads trace context Temporal carries as workflow/activity headers and turns it back
        # into spans, so a trace started by whatever called start_workflow (an API request, in
        # Milestone 07's case) continues through workflow and activity execution here rather
        # than starting a disconnected trace of its own.
        interceptors=[TracingInterceptor()],
    )
    worker = Worker(
        client,
        task_queue=settings.temporal.task_queue,
        workflows=list(WORKFLOWS),
        activities=list(ACTIVITIES),
    )

    logger.info(
        "temporal worker starting",
        extra={
            "operation": "startup",
            "task_queue": settings.temporal.task_queue,
            "namespace": settings.temporal.namespace,
        },
    )
    async with worker:
        await shutdown_event.wait()
    logger.info("temporal worker stopping", extra={"operation": "shutdown"})
