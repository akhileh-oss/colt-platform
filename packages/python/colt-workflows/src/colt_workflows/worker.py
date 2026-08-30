"""The Temporal worker process (CLAUDE.md §3.3, §24, §58).

`run_worker` is factored out from `__main__` so both the real process entry point and tests
(hermetic and real-infra alike) construct a worker the same way — the durability test in
`tests/integration` runs this exact function in a subprocess, not a test-only stand-in.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from temporalio.client import Client
from temporalio.worker import Worker

from colt_config import Settings, get_settings
from colt_observability import get_logger
from colt_workflows.activities.example import greet
from colt_workflows.workflows.example import ExampleWorkflow

logger = get_logger(__name__)

#: Every workflow and activity this worker executes. Milestone 06 has exactly one of each —
#: later milestones register their own here as they add real workflows.
WORKFLOWS: Sequence[type] = (ExampleWorkflow,)
ACTIVITIES: Sequence[Any] = (greet,)


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

    client = await Client.connect(settings.temporal.address, namespace=settings.temporal.namespace)
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
