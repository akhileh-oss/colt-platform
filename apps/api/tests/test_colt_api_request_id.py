"""Request identity and traceability (CLAUDE.md §92)."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from colt_api.errors import ColtError, ErrorCode
from colt_observability import configure_logging


def test_a_request_id_is_generated_and_returned(client: TestClient) -> None:
    response = client.get("/live")
    request_id = response.headers["X-Request-ID"]
    assert request_id.startswith("req_")


def test_each_request_gets_a_distinct_id(client: TestClient) -> None:
    first = client.get("/live").headers["X-Request-ID"]
    second = client.get("/live").headers["X-Request-ID"]
    assert first != second


def test_an_inbound_request_id_is_honoured(client: TestClient) -> None:
    """Lets a trace span services rather than restarting at our boundary."""
    response = client.get("/live", headers={"X-Request-ID": "req_from_caller_123"})
    assert response.headers["X-Request-ID"] == "req_from_caller_123"


@pytest.mark.parametrize(
    "hostile",
    [
        'evil"\n{"level":"FATAL"}',  # log-injection attempt
        "a" * 500,  # overlong
        "has spaces",
        "../../etc/passwd",
        "",
    ],
)
def test_an_unsafe_inbound_request_id_is_replaced_not_cleaned(
    client: TestClient, hostile: str
) -> None:
    """The header reaches logs, so a malformed value is replaced outright, never salvaged."""
    response = client.get("/live", headers={"X-Request-ID": hostile})
    returned = response.headers["X-Request-ID"]
    assert returned.startswith("req_")
    assert returned != hostile
    # No fragment of the hostile value survives into the accepted ID.
    assert "evil" not in returned and "passwd" not in returned


def test_the_request_id_appears_in_the_error_body(app: FastAPI) -> None:
    """A user-visible failure must map to a searchable request ID (§92)."""

    @app.get("/api/v1/_boom")
    async def boom() -> None:
        raise ColtError(ErrorCode.CONFLICT, "Already exists.")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/_boom", headers={"X-Request-ID": "req_trace_me"})

    assert response.status_code == 409
    assert response.json()["error"]["request_id"] == "req_trace_me"
    assert response.headers["X-Request-ID"] == "req_trace_me"


def test_the_request_id_appears_in_the_access_log(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    # The stream handler binds sys.stdout when it is built, which happened during fixture
    # setup. Rebind it to the stdout capsys is capturing right now.
    configure_logging(level="INFO", service_name="colt-api")
    client.get("/live", headers={"X-Request-ID": "req_logged"})
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("{")]
    completed = [
        json.loads(ln) for ln in lines if json.loads(ln).get("message") == "request completed"
    ]
    assert completed, "no access log line was emitted"
    assert completed[-1]["request_id"] == "req_logged"
    assert completed[-1]["operation"] == "GET /live"
    assert completed[-1]["status"] == 200
    assert "latency_ms" in completed[-1]
