# Workflow architecture

> Skeleton established in Milestone 00; populated in Milestone 06 (Temporal foundation) and
> Milestone 18 (outreach workflow). Specification: `CLAUDE.md` §24.

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
observability and input/output schemas (`CLAUDE.md` §24.2).

## 4. `LeadOutreachWorkflow`

The required shape is specified in `CLAUDE.md` §24.3.

## 5. Idempotent send

Send keys derive from stable business identifiers —
`organization_id + campaign_id + lead_id + sequence_step_id` — and the provider's own idempotency
key is passed where supported. A retry must never send a second email (`CLAUDE.md` §2.9, §24.4).
