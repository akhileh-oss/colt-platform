# Workflow architecture

> Skeleton established in Milestone 00. Milestone 06 built the worker process, graceful
> shutdown, and a real proof that a workflow survives a worker restart. `LeadOutreachWorkflow`
> itself (§24.3) is still Milestone 18's — this milestone proved the harness, not the product
> workflow. Specification: `CLAUDE.md` §24.

## 1. Why Temporal

Long-running orchestration — multi-day sequences, approval waits, reply branching — is durable
state, not process memory. Temporal workflows are the source of truth for that orchestration
(`CLAUDE.md` §3.3).

## 2. Determinism

Workflows may call activities, wait on timers, wait on signals, branch on stored deterministic
state and retry under explicit policies. They may not perform network calls, touch a database
driver, rely on process memory, generate non-deterministic IDs outside the SDK's mechanisms, or
read wall-clock time outside Temporal APIs (`CLAUDE.md` §24.1).

Sequencing is workflow logic, not agent reasoning. "Wait three days before follow-up" is code;
"which angle will this buyer care about" is reasoning (`CLAUDE.md` §2.5).

## 3. Activities

Every activity declares timeout, retryable and non-retryable errors, idempotency strategy,
observability and input/output schemas (`CLAUDE.md` §24.2). `colt_workflows.activities.example`
(Milestone 06) is the first instance of this pattern: a non-retryable failure is raised as
`ApplicationError(..., non_retryable=True)` from inside the activity itself — the activity owns
that decision, rather than every caller having to list the error type in its own retry policy.

## 4. The worker process

`colt_workflows.worker.run_worker` connects to Temporal and runs until a caller-supplied
`asyncio.Event` is set; `python -m colt_workflows` (`make worker`) wires `SIGTERM`/`SIGINT` to
that event so a container stop or `Ctrl-C` drains in-flight activity tasks through the SDK's own
`async with worker:` shutdown rather than dropping them (`CLAUDE.md` §58).

`run_worker` is factored out from `__main__` specifically so the real entry point and tests
construct a worker identically. `tests/integration/test_workflow_durability.py` runs this exact
function, unmodified, in a subprocess it kills and replaces mid-workflow — proving Milestone 06's
acceptance criterion (a workflow survives a worker restart) against a real Temporal server, not
asserted from the SDK's own documentation. `tests/workflows/test_example_workflow.py` covers the
workflow's logic separately, against Temporal's in-process time-skipping test environment — fast,
but with no worker process to kill, so it cannot substitute for the durability test.

A real bug surfaced only by the durability test, not the hermetic one: an early version of the
example activity logged with `extra={"name": ...}`, which collides with `LogRecord`'s own
reserved `name` attribute and crashes stdlib `logging.Logger.makeRecord` with a `KeyError`. The
hermetic test's process never calls `configure_logging()`, so the logger's effective level
silently no-ops the `.info()` call before it reaches `makeRecord` — passing by accident. The real
worker subprocess does configure logging, so the crash was real and reproducible there. Fixed by
naming the field `greeted_name` instead.

## 5. `LeadOutreachWorkflow`

The required shape is specified in `CLAUDE.md` §24.3.

## 6. Idempotent send

Send keys derive from stable business identifiers —
`organization_id + campaign_id + lead_id + sequence_step_id` — and the provider's own idempotency
key is passed where supported. A retry must never send a second email (`CLAUDE.md` §2.9, §24.4).
`Message.idempotency_key` (Milestone 05) already carries a partial-unique index scoped to
`(organization_id, idempotency_key)`, ready for the send activity Milestone 18 adds.
