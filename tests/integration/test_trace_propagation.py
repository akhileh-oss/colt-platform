"""Milestone 07's acceptance criterion, proven literally: "A test request can be traced
through API → workflow → activity → DB" (CLAUDE.md §68).

The API request runs in-process via `TestClient` (the pattern `test_auth_end_to_end.py`
established: real Keycloak, real Postgres, no mocks). The workflow and its activities run in a
real `python -m colt_workflows` worker *subprocess* — a genuinely separate process, connected to
the API only through the real local Temporal server and the trace context Temporal carries as
request headers (`temporalio.contrib.opentelemetry.TracingInterceptor`, wired into both the
worker's client and the API's per-request Temporal client).

Correlation is checked through structured JSON logs rather than a captured-span exporter:
`POST /api/v1/observability/trace-check` returns the trace ID its own request span carried, and
every log line the worker's activities emit carries the same field automatically
(`colt_observability.context.get_log_context`, Milestone 07). The two matching is direct
evidence the trace actually crossed the real Temporal RPC boundary between two OS processes —
not something asserted from SDK documentation.

Requires a real Postgres, Keycloak and Temporal server (`make dev`). Marked `integration`.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from colt_api.app import create_app
from colt_db.dev_seed import seed_dev_organizations_and_users
from colt_db.session import get_default_engine

KEYCLOAK_TOKEN_URL = "http://localhost:8081/realms/colt/protocol/openid-connect/token"  # noqa: S105 - a URL, not a credential
_REPO_ROOT = Path(__file__).resolve().parents[2]
_UV = shutil.which("uv")
if _UV is None:
    raise RuntimeError("uv must be on PATH to run this test — it spawns a real worker process.")


@pytest_asyncio.fixture(autouse=True)
async def _seed_identities() -> None:
    """Same rationale as `test_auth_end_to_end.py`: `_clean_tables` truncates every test, so
    seeding happens per-test rather than relying on `make seed` having run out of band."""
    engine = get_default_engine()
    async with engine.begin() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)
        await seed_dev_organizations_and_users(session)


def _fetch_token(username: str, password: str) -> str:
    response = httpx.post(
        KEYCLOAK_TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": "colt-api",
            "client_secret": "colt-api-secret",
            "username": username,
            "password": password,
            "scope": "openid",
        },
        timeout=10,
    )
    response.raise_for_status()
    token: str = response.json()["access_token"]
    return token


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def trace_check_worker() -> Iterator[subprocess.Popen[str]]:
    """A real `python -m colt_workflows` worker, on the shared `colt-main` task queue the API's
    per-request Temporal client also uses (`TemporalSettings.task_queue`) — this is the one test
    that needs the two to actually agree on a queue, unlike the durability test's disposable
    per-run queue name."""
    assert _UV is not None  # narrowed at import time; re-asserted here for mypy's benefit
    proc = subprocess.Popen(  # noqa: S603 - a fixed, fully-static argv; nothing here is
        # untrusted input reaching argv or a shell.
        [_UV, "run", "python", "-m", "colt_workflows"],
        cwd=_REPO_ROOT,
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(3)  # give it time to connect and start polling before the test starts a workflow
    try:
        yield proc
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)


def _read_worker_log_lines(
    proc: subprocess.Popen[str], *, timeout: float = 15.0
) -> list[dict[str, object]]:
    """Read whatever the worker has printed so far, parsing each JSON log line.

    The worker keeps running (and printing) after the workflow completes, so this reads with an
    overall deadline rather than waiting for EOF, which would hang until the process is killed.
    """
    assert proc.stdout is not None
    lines: list[dict[str, object]] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = proc.stdout.readline()
        if not raw:
            time.sleep(0.1)
            continue
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError:
            continue  # a non-JSON line (e.g. a gRPC warning) — not what this test is reading for
        if any(line.get("operation") == "count_organizations" for line in lines):
            break
    return lines


@pytest.mark.asyncio
async def test_trace_spans_api_workflow_activity_and_database(
    api_client: TestClient, trace_check_worker: subprocess.Popen[str]
) -> None:
    token = _fetch_token("alice", "alice-dev-password")

    response = api_client.post(
        "/api/v1/observability/trace-check",
        json={"name": "Trace Test"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["greeting"] == "Hello, Trace Test!"
    api_trace_id = body["trace_id"]
    assert api_trace_id, "the API must have had an active trace span for this request"

    worker_lines = _read_worker_log_lines(trace_check_worker)
    activity_lines = [
        line for line in worker_lines if line.get("operation") == "count_organizations"
    ]
    assert activity_lines, (
        "the worker never logged the DB-touching activity — see captured output above for why"
    )

    assert activity_lines[0]["trace_id"] == api_trace_id, (
        "the activity ran under a different trace than the API request that started it — "
        "trace context did not propagate across the Temporal RPC boundary"
    )
