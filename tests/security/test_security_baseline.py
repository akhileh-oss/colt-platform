"""Security headers and log redaction (CLAUDE.md §40's "security headers" Build item and
"Never... log bearer tokens" / "store plaintext passwords" / "return provider OAuth refresh
tokens" Never items, §93) — security-suite sentinels, not duplicates of the exhaustive
feature-level suites that already exist: `apps/api/tests/test_colt_api_middleware.py` covers
`SECURITY_HEADERS` case by case, and `packages/python/colt-observability/tests/
test_colt_observability_redaction.py` covers `redact`/`is_sensitive_key` case by case. This
file's job is narrower and different: prove the two invariants §40 actually names — every
response carries the full header set, and every credential CLAUDE.md names as a "Never log"
item is still caught by the redactor — hold from `tests/security/`'s own vantage point, so a
regression here is caught even if either feature-level suite is ever reorganized or weakened.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from colt_api.app import create_app
from colt_api.middleware import SECURITY_HEADERS
from colt_api.readiness import readiness_registry
from colt_config import Settings
from colt_observability import is_sensitive_key, redact

pytestmark = pytest.mark.security


def test_every_response_carries_the_full_security_header_set() -> None:
    app = create_app(Settings())
    readiness_registry.clear()

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/live")

    readiness_registry.clear()

    for name, value in SECURITY_HEADERS.items():
        assert response.headers.get(name) == value, f"missing or wrong {name!r} header"


@pytest.mark.parametrize(
    "key",
    [
        "Authorization",
        "access_token",
        "password",
        "refresh_token",
        "db_password",
        "client_secret",
    ],
)
def test_every_claude_md_named_never_log_field_is_redacted(key: str) -> None:
    """§40's "Never" list names bearer tokens, plaintext passwords, and OAuth refresh tokens
    explicitly — this is the direct proof that each one is still a sensitive key today."""
    assert is_sensitive_key(key)
    assert redact({key: "super-secret-value"})[key] == "[REDACTED]"
