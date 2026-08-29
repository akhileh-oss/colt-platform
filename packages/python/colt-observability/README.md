# colt-observability

Structured logging, tracing and metrics helpers (`CLAUDE.md` §35).

```python
from colt_observability import bind_log_context, configure_logging, get_logger

configure_logging(level="INFO", service_name="colt-api")
logger = get_logger(__name__)

with bind_log_context(request_id="req_1", organization_id="org_1"):
    logger.info("lead qualified", extra={"operation": "qualify", "lead_id": "lead_9"})
```

Every record is one JSON object carrying the correlation fields bound at the time (§35.1).

## Redaction is automatic

Records pass through `redact()` before serialisation, so a value under a key like `api_key`,
`authorization`, `password` or `client_secret` never reaches the log — including nested inside
dictionaries and lists. This is deliberately not left to the caller: §93 requires that redaction
not depend on every developer remembering it.

Exceptions are logged as type and message only. Tracebacks belong in the exception tracker, not in
application logs (§25.4).

## Context fields

Only the fields named in `CONTEXT_FIELDS` (§35.1) can be bound. A typo raises rather than
silently creating a field nothing searches for.

## Not yet here

OpenTelemetry tracing and metrics export (§35.2) land in Milestone 07. This package currently
provides logging, redaction and correlation context.
