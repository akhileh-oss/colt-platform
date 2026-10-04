# Colt — AI Revenue Operating System

Colt continuously discovers high-value prospects, researches them against verifiable evidence,
detects why-now buying signals, qualifies and prioritises opportunities, generates evidence-backed
outreach, orchestrates conversations across approved channels, and learns from revenue outcomes.

It is a **deterministic software platform with AI reasoning components** — not an autonomous agent
swarm. Software owns sequencing, state and safety; models are used where judgement is genuinely
required.

> **[`CLAUDE.md`](./CLAUDE.md) is the authoritative engineering specification.** It governs
> architecture, standards, milestones and acceptance criteria. Where this README and `CLAUDE.md`
> disagree, `CLAUDE.md` wins.

---

## Status

**Milestone 08 — AI Gateway: complete** (one acceptance step unverified — see below).

`make dev` brings up the full local stack — Postgres with pgvector, Redis, Temporal and its UI,
MinIO, Mailpit, Keycloak and an OpenTelemetry collector — and verifies every service is serving.

The API authenticates every protected route against real Keycloak-issued JWTs, resolves the
caller's organization and role from the database rather than trusting the token, enforces
per-permission authorization, and scopes every tenant query through two independent layers — an
application-layer repository base class and PostgreSQL Row-Level Security, now covering all
eleven tenant-owned tables. `Organization`, `User`, `Company`, `Person`, `Signal`, `Evidence`,
`Lead`, `Campaign`, `Message`, `Conversation`, `Opportunity` and `AuditLog` are real domain
entities and database tables, with Alembic migrations and a seeded local dataset
(`make migrate && make seed`). A Temporal worker (`make worker`) runs real workflows against the
local Temporal server, with a proven-durable example workflow — killing the worker mid-workflow
and starting a fresh one still completes it correctly, from server-tracked state rather than
worker memory. Every request, workflow, activity and database query is traced with
OpenTelemetry and correlated by `trace_id` in structured JSON logs — proven by one real request
whose trace ID appears in both the API's own log line and a DB-touching Temporal activity's, in
a genuinely separate worker process.

The web app is a Next.js operator console with a persistent shell, navigation to every feature
area, and a typed client generated from that OpenAPI contract (`@colt/api-client`). Every feature
page except the dashboard's system health panel is an honest placeholder — the schema, repositories
and worker exist, but no route yet reads or writes through them, and the web app has no login
flow yet, so there is little else real to show.

`colt_ai.AnthropicGateway` is the one place allowed to call the Anthropic SDK directly: it routes
a `ModelClass` to a configured model ID, validates structured output against a Pydantic schema
server-side, records usage and cost from every response, classifies provider errors into Colt's
own error taxonomy, and never passes prompt or response content to a log line or span attribute.
**One caveat:** no real Anthropic API key exists in this environment, so Milestone 08's literal
acceptance criterion — "one deterministic test call produces a validated structured result and
records usage metadata" — is proven against a fake response at the `AsyncAnthropic` client
boundary, not a real network call to the Anthropic API. Every other line of the gateway's own
logic (routing, usage accounting, error classification, telemetry, redaction) runs for real in
that test; only the actual provider round-trip is substituted.

| Milestone | Scope                                 | Status                         |
| --------- | ------------------------------------- | ------------------------------ |
| 00        | Repository bootstrap                  | ✅ Complete                    |
| 01        | Local infrastructure (Docker Compose) | ✅ Complete                    |
| 02        | FastAPI foundation                    | ✅ Complete                    |
| 03        | Next.js foundation                    | ✅ Complete                    |
| 04        | Authentication + multi-tenancy        | ✅ Complete                    |
| 05        | Database + domain foundation          | ✅ Complete                    |
| 06        | Temporal foundation                   | ✅ Complete                    |
| 07        | Observability foundation              | ✅ Complete                    |
| 08        | AI gateway                            | ✅ Complete (see caveat above) |
| 09–30     | See [`CLAUDE.md` §68](./CLAUDE.md)    | Not started                    |

---

## Requirements

| Tool                             | Version | Purpose                                  |
| -------------------------------- | ------- | ---------------------------------------- |
| Python                           | ≥ 3.12  | Backend, AI, workflows                   |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.8   | Python dependency + workspace management |
| Node.js                          | ≥ 22    | Frontend toolchain                       |
| [pnpm](https://pnpm.io/)         | 10.x    | Node workspace management                |
| Docker + Compose                 | recent  | Local infrastructure (from Milestone 01) |
| GNU Make                         | ≥ 4     | Developer entry points                   |

`uv` provisions the correct Python automatically — a system Python 3.12 is not required.

---

## Getting started

```bash
git clone git@github.com:akhileh-oss/colt-platform.git
cd colt-platform

cp .env.example .env      # placeholders only; never commit .env
make install              # uv sync + pnpm install
make check                # lint, typecheck, test, security
```

```bash
make dev          # start the local stack, then verify it
make api          # run the API on http://localhost:8000
make web          # run the web app on http://localhost:3000
make worker       # run the Temporal worker
make test-e2e     # Playwright — builds and starts the API and web app itself
```

Cold start takes about 30 seconds. `make dev` validates prerequisites, refuses to run if any
outbound side-effect flag is enabled (`CLAUDE.md` §6.4), starts the containers, provisions the
MinIO bucket, health-checks every service, and prints the local URLs. Targets belonging to a later
milestone exit with a message naming it rather than silently pretending to succeed (§0.4).

Run `make help` to list every target.

### Local services

| Service                     | URL                                                  | Credentials                 |
| --------------------------- | ---------------------------------------------------- | --------------------------- |
| Temporal UI                 | http://localhost:8080                                | —                           |
| Mailpit (all outbound mail) | http://localhost:8025                                | —                           |
| MinIO console               | http://localhost:9001                                | `minioadmin` / `minioadmin` |
| Keycloak                    | http://localhost:8081                                | `admin` / `admin`           |
| Postgres (migrations)       | `postgresql://colt:colt@localhost:5432/colt`         | `colt` / `colt`             |
| Postgres (application)      | `postgresql://colt_app:colt_app@localhost:5432/colt` | `colt_app` / `colt_app`     |
| Redis                       | `redis://localhost:6379/0`                           | —                           |
| OTLP gRPC / HTTP            | `localhost:4317` / `localhost:4318`                  | —                           |
| Web                         | http://localhost:3000                                | `make web`                  |
| API                         | http://localhost:8000                                | `make api`                  |
| API docs                    | http://localhost:8000/docs                           | `make api`                  |

Those credentials are local-only development defaults, deliberately weak and deliberately
committed. They exist nowhere but your machine.

---

## Repository layout

```text
apps/
  api/                    FastAPI application — API boundary and composition root
  web/                    Next.js operator console
packages/
  python/
    colt-domain/          Entities, value objects, invariants, deterministic rules
    colt-application/     Use cases and application services
    colt-config/          Typed settings (ADR-0003)
    colt-agents/          Agent definitions, prompts, runtime integration
    colt-workflows/       Temporal workflows and activities
    colt-integrations/    Provider adapters
    colt-db/              SQLAlchemy models, repositories, migrations
    colt-policy/          Authorization and business-safety policy engine
    colt-observability/   Logging, tracing, metrics helpers
    colt-ai/              AI gateway: Anthropic client wrapper, model routing, usage accounting
  typescript/
    ui/                   Shared UI primitives
    api-client/           Typed API client generated from OpenAPI
infrastructure/           Docker, Terraform, per-environment configuration
docs/                     Architecture, decisions (ADRs), security, operations
prompts/                  Versioned, source-controlled agent prompts
tests/                    unit, integration, e2e, workflows, security, evals
scripts/                  Developer and CI scripts
```

### Layering

Dependencies point inward (`CLAUDE.md` §5). The domain package depends on nothing and must never
import FastAPI, SQLAlchemy, the Anthropic SDK, the Temporal SDK, Redis or any provider module.
The workspace dependency graph declares this shape:

```text
domain  ←  policy  ←  application  ←  workflows
   ↑                      ↑              ↑
   └──  db, integrations, agents  ────────┘
```

---

## Commands

| Command                 | Does                                                         |
| ----------------------- | ------------------------------------------------------------ |
| `make install`          | Install Python and Node dependencies                         |
| `make format`           | Format Python (ruff) and TypeScript (prettier)               |
| `make lint`             | Lint and check formatting across both stacks                 |
| `make typecheck`        | mypy `--strict` and TypeScript project references            |
| `make test`             | Unit tests (pytest + vitest)                                 |
| `make test-workflows`   | Temporal workflow tests (in-process time-skipping)           |
| `make test-integration` | Integration tests (requires `make dev` + `make migrate`)     |
| `make test-e2e`         | Playwright — builds and starts the API and web app itself    |
| `make security`         | `pip-audit`, `pnpm audit`, and secret scanning               |
| `make check`            | Everything above — the CI gate                               |
| `make api-client`       | Regenerate the typed TS client from the API's OpenAPI schema |
| `make clean`            | Remove caches and build artifacts                            |

---

## Engineering rules that bite early

- **No secrets in the repository.** `.env` is git-ignored; `.env.example` holds placeholders only.
  `make security` scans every tracked file and fails on a new finding (`CLAUDE.md` §7.2, §40).
- **Evidence before assertions.** Any factual claim used in outreach must trace to a stored source
  with a URL, observation date and confidence. Never invent a source (`CLAUDE.md` §2.6, §20).
- **Claude never touches the database or the network directly.** Reasoning goes through typed
  tools, a policy check, then application services (`CLAUDE.md` §2.3, §2.4).
- **Multi-tenancy from day one.** Every tenant-owned record carries `organization_id`, and a
  client-supplied organization ID is never trusted (`CLAUDE.md` §2.8, §27). Enforced twice: an
  application-layer repository base class that cannot query unscoped, and PostgreSQL Row-Level
  Security. The API connects as the restricted `colt_app` role, never the `colt` superuser Alembic
  uses for migrations — a superuser bypasses RLS unconditionally, silently defeating it.
- **Retrieved content is untrusted data**, never instructions — web pages, emails and CRM notes can
  carry prompt injection (`CLAUDE.md` §41).
- **The domain layer stays clean.** `colt-domain` may not import FastAPI, SQLAlchemy, the
  Anthropic or Temporal SDKs, Redis, httpx or a cloud SDK. This is enforced by
  `packages/python/colt-domain/ruff.toml`, so a violation fails `make lint` (`CLAUDE.md` §5.3).
- **Architecture changes need an ADR.** See [`docs/decisions/`](./docs/decisions/) (`CLAUDE.md` §64).

---

## Documentation

| Document                                                                                     | Covers                          |
| -------------------------------------------------------------------------------------------- | ------------------------------- |
| [`CLAUDE.md`](./CLAUDE.md)                                                                   | The authoritative specification |
| [`docs/architecture/ARCHITECTURE.md`](./docs/architecture/ARCHITECTURE.md)                   | System shape and layering       |
| [`docs/architecture/DOMAIN_MODEL.md`](./docs/architecture/DOMAIN_MODEL.md)                   | Entities and state machines     |
| [`docs/architecture/AGENT_ARCHITECTURE.md`](./docs/architecture/AGENT_ARCHITECTURE.md)       | Agents, runtime, tools          |
| [`docs/architecture/WORKFLOW_ARCHITECTURE.md`](./docs/architecture/WORKFLOW_ARCHITECTURE.md) | Temporal orchestration          |
| [`docs/security/SECURITY_MODEL.md`](./docs/security/SECURITY_MODEL.md)                       | Threat model and controls       |
| [`docs/operations/RUNBOOK.md`](./docs/operations/RUNBOOK.md)                                 | Day-to-day operations           |
| [`docs/operations/DEPLOYMENT.md`](./docs/operations/DEPLOYMENT.md)                           | Release and rollback            |
| [`docs/operations/INCIDENTS.md`](./docs/operations/INCIDENTS.md)                             | Incident response               |
| [`docs/decisions/`](./docs/decisions/)                                                       | Architecture Decision Records   |

---

## Licence

Proprietary. © Colt & Co.
