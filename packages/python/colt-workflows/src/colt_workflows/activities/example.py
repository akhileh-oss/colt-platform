"""The foundation milestone's one activity — proves the worker harness end to end.

Not part of any real product workflow (`LeadOutreachWorkflow`, §24.3, lands in Milestone 18).
This exists solely to give `ExampleWorkflow` something real to call, so Milestone 06's
acceptance criterion — a durable workflow that survives a worker restart — has actual activity
execution, retries and observability to prove, not just a bare timer.
"""

from __future__ import annotations

from dataclasses import dataclass

from temporalio import activity
from temporalio.exceptions import ApplicationError

from colt_observability import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExampleActivityInput:
    """Explicit input schema (CLAUDE.md §24.2) — the data converter serializes this as JSON."""

    name: str


@activity.defn
async def greet(input: ExampleActivityInput) -> str:
    """Deterministic, side-effect-free by design: safe to retry without an idempotency key."""
    # "greeted_name", not "name" — LogRecord already has its own reserved `name` attribute (the
    # logger's own name), and passing `extra={"name": ...}` crashes stdlib logging's
    # makeRecord() with a KeyError before the record is even built. Caught here by actually
    # running this activity against a real worker, not just the hermetic workflow test, which
    # never lets the log line's own JSON formatting run into contact with the real handler.
    logger.info(
        "executing example activity", extra={"operation": "greet", "greeted_name": input.name}
    )
    if not input.name.strip():
        # Non-retryable (§24.2): a blank name will never become valid by retrying. Raised as
        # ApplicationError(non_retryable=True) rather than a bare ValueError so the activity
        # itself owns this decision, instead of relying on every caller's retry policy to list
        # it in non_retryable_error_types.
        raise ApplicationError("name must not be blank", non_retryable=True)
    return f"Hello, {input.name}!"
