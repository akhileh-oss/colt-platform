"""Milestone 06's acceptance criterion, proven literally: a workflow survives a worker restart.

Spawns two real `python -m colt_workflows` worker subprocesses against the real local Temporal
server (`make dev`) — not the in-process time-skipping environment `tests/workflows` uses, which
has no worker process to kill. Worker A starts, executes the workflow's activity, and begins its
timer; it is then terminated (SIGTERM, the same signal a container orchestrator sends). While no
worker is running at all, the workflow's state exists only in the Temporal server. Worker B, a
fresh process, is started and picks the workflow back up from server-tracked history — proving
durability actually holds, not just that the SDK docs say it should.

Requires a real Temporal server (`make dev`). Marked `integration`.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import subprocess
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from temporalio.client import Client

from colt_workflows.workflows.example import ExampleWorkflow

TEMPORAL_ADDRESS = "localhost:7233"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_UV = shutil.which("uv")
if _UV is None:
    raise RuntimeError("uv must be on PATH to run this test — it spawns real worker processes.")


def _spawn_worker(*, task_queue: str) -> subprocess.Popen[bytes]:
    assert _UV is not None  # narrowed at import time; re-asserted here for mypy's benefit
    env = os.environ | {"TEMPORAL_TASK_QUEUE": task_queue}
    return subprocess.Popen(  # noqa: S603 - a fixed, fully-static argv; task_queue only ever
        # reaches an env var value, never argv or a shell, so there is nothing here for
        # untrusted input to inject into.
        [_UV, "run", "python", "-m", "colt_workflows"],
        cwd=_REPO_ROOT,
        env=env,
    )


def _stop_worker(proc: subprocess.Popen[bytes], *, timeout: float = 10.0) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=timeout)


@pytest_asyncio.fixture
async def temporal_client() -> AsyncIterator[Client]:
    yield await Client.connect(TEMPORAL_ADDRESS, namespace="default")


@pytest.mark.asyncio
async def test_example_workflow_survives_a_worker_restart(temporal_client: Client) -> None:
    task_queue = f"durability-test-{uuid.uuid4()}"
    workflow_id = f"durability-test-{uuid.uuid4()}"

    worker_a = _spawn_worker(task_queue=task_queue)
    try:
        # Give worker A time to connect and start polling before there is any work queued.
        await asyncio.sleep(3)

        handle = await temporal_client.start_workflow(
            ExampleWorkflow.run,
            args=["Restart Test"],
            id=workflow_id,
            task_queue=task_queue,
        )

        # Long enough that worker A has certainly executed the activity and entered its timer
        # (fast, sub-second) before it is killed, and short enough to keep the test fast.
        await asyncio.sleep(3)
    finally:
        _stop_worker(worker_a)

    # No worker at all is running here. If durability depended on worker process memory rather
    # than the Temporal server, the workflow would be stuck forever from this point on.
    await asyncio.sleep(1)

    worker_b = _spawn_worker(task_queue=task_queue)
    try:
        result = await asyncio.wait_for(handle.result(), timeout=30)
    finally:
        _stop_worker(worker_b)

    assert result == "Hello, Restart Test!"
