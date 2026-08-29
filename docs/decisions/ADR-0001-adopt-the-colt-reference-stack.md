# ADR-0001 — Adopt the Colt reference stack

## Context

Colt is an AI revenue platform that must run continuously, act on real customer data, and perform
irreversible external side effects — sending email, writing to a CRM, creating calendar events. The
engineering risks that matter are duplicate or wrongful sends, fabricated claims in outbound
messaging, cross-tenant data leakage, and unexplainable AI actions.

`CLAUDE.md` §3 fixes a technology stack to remove per-feature relitigation of these choices. This
ADR records that stack as a deliberate decision with its reasoning, so that future deviation is
argued against something rather than assumed.

## Decision

We will build Colt on the stack specified in `CLAUDE.md` §3:

- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, httpx, `uv`.
- **Frontend:** Next.js, React, TypeScript, Tailwind, shadcn/ui, TanStack Query, `pnpm`.
- **Orchestration:** Temporal, as the source of truth for long-running orchestration.
- **Data:** PostgreSQL as the system of record, pgvector for semantic representations, Redis for
  cache/locks/ephemeral coordination, S3-compatible object storage.
- **AI:** the Anthropic API behind a Colt-owned AI gateway and agent runtime, with a typed tool
  registry. LangChain/LangGraph will **not** be a mandatory dependency.
- **Observability:** OpenTelemetry, structured JSON logs, Prometheus-compatible metrics, Sentry.
- **Quality gates:** Ruff, mypy `--strict`, pytest, ESLint, Prettier, Vitest, Playwright.

Layer boundaries are enforced structurally by the workspace dependency graph, not by convention
alone: `colt-domain` depends on nothing, so it cannot import a framework, ORM or SDK.

## Alternatives considered

**A single Django or Rails monolith.** Faster to a first screen, but the domain layer would be
welded to the ORM, and durable multi-day orchestration would fall back to cron plus database flags
— precisely the "cron script pretending to be a workflow engine" that `CLAUDE.md` §1.2 rules out.

**Celery instead of Temporal.** Celery is a task queue, not a workflow engine. Multi-day sequences
with approval waits, reply branching and replayable history would have to be rebuilt on top of it,
badly. Temporal provides durable execution and replay as primitives, which is what the outreach
loop actually needs.

**LangChain/LangGraph as the agent framework.** Rejected as a _mandatory_ dependency. Colt's hard
requirements — per-run cost accounting, prompt versioning, tool permission filtering by agent,
policy checks before side effects, and full run attribution — are cross-cutting and must be owned
by Colt's own runtime. A framework layer here would obscure the audit trail rather than provide it.
Direct Anthropic SDK use behind a Colt gateway keeps that control. This is not a judgement that the
libraries are bad; it is that the abstraction boundary is in the wrong place for this system.

**MongoDB or a vector database as the system of record.** Rejected. The domain is highly
relational, and the correctness properties that matter — uniqueness of a send, foreign-key
integrity, transactional state transitions, idempotency keys — are exactly what a relational
database enforces. Vector storage serves retrieval, never truth (`CLAUDE.md` §19.1).

**TypeScript across the whole stack.** Attractive for one language and shared types. Rejected
because the AI, workflow and data-processing ecosystem Colt depends on is materially stronger in
Python, and the OpenAPI-generated client already gives type safety across the boundary without a
shared runtime.

## Consequences

- Two toolchains must be maintained (`uv` and `pnpm`), and CI must run both. `make check` hides
  that split behind one command.
- Contributors need Python and TypeScript fluency.
- Temporal is operational surface area — a server, workers and a UI — from Milestone 01 onward.
  This is accepted as the cost of durable orchestration.
- Owning the AI gateway and agent runtime means we write and maintain retry, cost accounting and
  tool-permission logic ourselves. That is deliberate: those are the parts we must be able to
  audit.
- Model IDs are configuration, never literals in business logic, so a model change is a deployment
  change rather than a code rewrite (`CLAUDE.md` §14.2).
- Reversing any element of this stack requires a superseding ADR.

## Status

Accepted — 2026-08-29
