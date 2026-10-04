# Architecture

> Skeleton established in Milestone 00. Sections are filled in as the milestones that build each
> layer land. `CLAUDE.md` remains the authoritative specification — this document explains **how
> the code actually realises it**, and must be updated whenever behaviour changes (`CLAUDE.md` §63).

## 1. System shape

Colt is a deterministic platform with AI reasoning components. Responsibilities are separated
absolutely (`CLAUDE.md` §2.1):

| Concern                              | Owner                         |
| ------------------------------------ | ----------------------------- |
| Reasoning                            | Claude, via the agent runtime |
| Controlled capabilities              | Typed tool registry           |
| Authorization and business safety    | Policy engine                 |
| Deterministic business logic         | Application services          |
| Business source of truth             | PostgreSQL                    |
| Durable orchestration                | Temporal                      |
| Cache, locks, ephemeral coordination | Redis                         |
| API boundary                         | FastAPI                       |
| Presentation                         | Next.js                       |

## 2. Layering

Dependencies point inward:

```text
Presentation → API/UI → Application → Domain → Ports → Infrastructure
```

The domain layer imports no framework, ORM, SDK or provider module (`CLAUDE.md` §5.3).

Two mechanisms carry this, and it is worth being precise about what each does. The workspace
dependency graph in each `pyproject.toml` **declares** the shape — it is the documentation of
intent — but it does not enforce it: `uv` installs every workspace package into a single shared
virtualenv, so at runtime any package can import anything present. Enforcement therefore comes
from `packages/python/colt-domain/ruff.toml`, which bans the forbidden modules outright via
`flake8-tidy-imports`. A forbidden import in the domain fails `make lint`, whether or not it is
used.

## 3. Package map

| Package              | Layer          | Responsibility                                                                    |
| -------------------- | -------------- | --------------------------------------------------------------------------------- |
| `colt-domain`        | Domain         | Entities, value objects, invariants, deterministic rules                          |
| `colt-application`   | Application    | Use cases, orchestration of domain objects and ports                              |
| `colt-policy`        | Application    | Authorization and business-safety decisions                                       |
| `colt-db`            | Infrastructure | SQLAlchemy models, repositories, migrations                                       |
| `colt-integrations`  | Infrastructure | Provider adapters behind domain-facing ports                                      |
| `colt-ai`            | Infrastructure | AI gateway: model routing, usage and cost accounting                              |
| `colt-agents`        | Application    | Agent definitions, prompts, runtime integration                                   |
| `colt-workflows`     | Application    | Temporal workflows and activities                                                 |
| `colt-observability` | Cross-cutting  | Logging, tracing, metrics                                                         |
| `colt-config`        | Cross-cutting  | Typed settings — see [ADR-0003](../decisions/ADR-0003-shared-settings-package.md) |
| `colt-api`           | Presentation   | FastAPI routers, DTOs, composition root                                           |

## 4. Request path

```text
client
  → RequestContextMiddleware      assign/validate X-Request-ID, bind log context
  → AccessLogMiddleware           one structured line per request
  → CORSMiddleware                origin allow-list
  → SecurityHeadersMiddleware     nosniff, DENY, no-referrer, COOP, Permissions-Policy
  → RequestSizeLimitMiddleware    reject oversized bodies
  → router (/api/v1 or probes)
  → dependency injection          settings, db session, JWT verifier, principal, permission check
  → endpoint
```

Protected routes add an authentication/authorization stage between routing and the endpoint
(`CLAUDE.md` §26, ADR-0005):

```text
  → bearer_token_provider          extract the token, or 401 if missing/malformed
  → jwt_verifier_provider          verify signature, issuer, audience, expiry against Keycloak
  → principal_provider             resolve organization + role from the User table, bind RLS
  → require_permission(Permission) 403 if the resolved role lacks the endpoint's permission
```

Keycloak establishes _who_ (a verified `sub` claim); it is never asked _which organization_ or
_what role_ — the `User` table is sole authority on both, so organization membership cannot be
forged by a token claim. `principal_provider` also binds the resolved organization onto the
database session's Row-Level Security context (`SET LOCAL app.current_organization_id`), so every
query the request makes afterward is scoped even if a repository call forgets an explicit filter.

Middleware is registered in reverse: the request context is added last so it is outermost and
every inner layer can read the request ID.

Failures leave through the handlers in `colt_api.errors`, which render the single §25.4 envelope.
The handler for an unhandled `Exception` runs inside Starlette's `ServerErrorMiddleware`, outside
our stack, so it resolves the request ID from the request scope rather than the logging context —
otherwise 500s, the responses that most need tracing, would carry no ID.

Readiness is a registry (`colt_api.readiness`) rather than a fixed list. Milestone 04 registered
the database check (a real `SELECT 1` against the pool). Milestone 06 built the Temporal worker
as its own independent process rather than something the API runs inline (§3.7: "Temporal
workers scale independently from FastAPI"), so there is no Temporal client in the API yet to add
a readiness check for — one is added once a route needs to start or signal a workflow
(Milestone 18).

### Database engine and connection pooling

`colt_db.session.get_default_engine()` uses `NullPool` — no connection reuse across checkouts —
rather than SQLAlchemy's default pooled engine. This is a testability constraint, not a production
performance choice made lightly: a pooled engine binds a connection to the event loop that first
checked it out, and FastAPI's `TestClient` (via `httpx2`) runs lifespan startup and per-request
handling on different internal loops, so a pooled engine fails cross-loop mid-suite. A real
deployed process has exactly one loop for its lifetime, so `NullPool` costs per-request connection
setup there and nothing else — an accepted tradeoff per `CLAUDE.md` §105's build-priority order
(reliability and testability before performance) at this stage of the build.

## 5. Temporal worker

`colt-workflows` is both the workflows/activities library and the worker process:
`python -m colt_workflows` (`make worker`) is its entry point, kept deliberately separate from
`apps/api` — Temporal workers scale independently from FastAPI (§3.7), and there is no
`apps/worker` directory in the canonical repository structure (§4) to put one in.

`colt_workflows.worker.run_worker` is factored out from `__main__` so the real process and tests
construct a worker identically: it connects to Temporal, builds a `Worker` over the configured
workflows/activities, and runs until a caller-supplied `asyncio.Event` is set. `__main__.py`
wires `SIGTERM`/`SIGINT` to that event; the SDK's own `async with worker:` shutdown then drains
in-flight activity tasks rather than dropping them (§58).

Milestone 06's acceptance criterion — a workflow surviving a worker restart — is proven by
running this exact function in a subprocess, killing it mid-workflow, and starting a fresh one
(`tests/integration/test_workflow_durability.py`). A separate, faster suite
(`tests/workflows/test_example_workflow.py`) covers workflow logic against Temporal's in-process
time-skipping test environment, which has no worker process to kill and so cannot substitute for
the durability proof.

## 6. Observability

Every process configures its own tracing, metrics and logging independently — `colt_api.app`'s
`create_app()` and `colt_workflows.worker`'s `run_worker()` each call
`colt_observability.configure_tracing()`/`configure_metrics()`, matching how each already calls
`configure_logging()` (`CLAUDE.md` §35). `FastAPIInstrumentor` instruments every HTTP route;
`SQLAlchemyInstrumentor` instruments every engine, in whichever process opens one; Temporal's own
`TracingInterceptor` (wired into both the worker's client and the API's per-request Temporal
client, `colt_api.dependencies.temporal_client_provider`) carries trace context across the
Temporal RPC boundary as headers, so a workflow a route starts continues the same trace rather
than beginning a disconnected one.

Trace correlation is structural in logs, not something a call site must remember: every log
record picks up `trace_id`/`span_id` from whatever OpenTelemetry span is active when it's
emitted (`colt_observability.context.get_log_context`), the same principle §93 already applies to
redaction. `POST /api/v1/observability/trace-check` exists solely to give Milestone 07's
acceptance criterion — a trace spanning API → workflow → activity → DB — a real request to prove
against; it starts `TraceCheckWorkflow` and is not a product endpoint, the way `/api/v1/meta` and
the health probes aren't. `tests/integration/test_trace_propagation.py` proves the whole chain
with two genuinely separate OS processes (an in-process API request via `TestClient`, and a real
`python -m colt_workflows` worker subprocess): the trace ID the API's response reports is
asserted to match the trace ID the worker's own DB-touching activity logged, independently,
across the real Temporal RPC boundary — not asserted from documentation.

A real bug this caught: `colt_workflows`'s top-level `__init__.py` used to re-export
`run_worker`/`ACTIVITIES`/`WORKFLOWS` for convenience. Since Python always initializes a parent
package before a submodule, any workflow file (`colt_workflows.workflows.example`, say) forced
that `__init__` to run too — and once it imported `colt_workflows.worker` (which needs
`colt_observability`'s full OpenTelemetry SDK and `colt_db`'s SQLAlchemy/asyncpg), Temporal's
workflow sandbox refused to validate the workflow at all, since a workflow must never import
real I/O-capable libraries directly. Fixed by keeping both `colt_workflows/__init__.py` and
`colt_workflows/activities/__init__.py` deliberately minimal, and wrapping the activity imports
inside actual workflow files with `workflow.unsafe.imports_passed_through()` — the SDK's own
documented escape hatch for imports a workflow file must make but the sandbox should trust
rather than validate.

## 7. AI Gateway

`colt_ai.AnthropicGateway` is the only place in Colt allowed to import the Anthropic SDK
directly (`CLAUDE.md` §8.2: "service code importing provider-specific implementations
directly" is forbidden everywhere else; §2.7 requires provider abstraction). Agents and
application services call the gateway, never `anthropic.*` — a provider change is a change to
one file, not a grep across the codebase.

`AnthropicGateway.generate_structured()` routes a `ModelClass` (`FAST`/`STANDARD`/`DEEP`/
`STRATEGIC`) to a concrete model ID through `AnthropicSettings.model_id_for()` (§14.1/§14.2 —
a model change is configuration, not a code rewrite), and validates the response against a
caller-supplied Pydantic schema server-side (`client.messages.parse(..., output_format=...)`)
rather than trusting free-text JSON. Timeout and retry are the SDK's own (`AnthropicSettings.
timeout_seconds`/`max_retries`, built on exponential backoff with jitter) — `colt_ai.errors.
classify()` turns whatever the SDK gives up on into Colt's own error taxonomy (§36), ordered
most-specific-first exactly as the SDK's own typed exception hierarchy requires (`APITimeoutError`
is a subclass of `APIConnectionError`; every HTTP-status error is a subclass of `APIStatusError`).

Usage and cost are recorded from `response.usage` on every call — `colt_ai.pricing.
estimate_cost_usd()` prices known model IDs and returns `None` rather than guessing for one it
doesn't recognise yet, and `llm_input_tokens`/`llm_output_tokens`/`provider_latency`/
`provider_rate_limits` (§35.2) are emitted as real OpenTelemetry instruments the moment this
milestone gives them something to measure — the first of §35.2's metrics beyond Milestone 07's
HTTP instruments to actually ship.

**Redaction here is what the gateway does _not_ log, not a filter on what it does.**
§93's `colt_observability.redact()` only catches sensitive _keys_ in structured payloads
(`api_key`, `password`, ...), never free text — a prompt or a model's response is exactly the
free text it can't see inside. So `AnthropicGateway` never passes `prompt`/`system`/response
content to a logger call or a span attribute in the first place; only metadata (model, token
counts, latency, request and agent-run IDs) reaches logs and traces (§35.1: "do not log ...
sensitive personal information unnecessarily").

`client` is an injectable constructor parameter — the same pattern `colt_observability.
configure_tracing()`'s injectable `exporter` established in Milestone 07 — so tests exercise
routing, usage accounting, error classification and the no-content-logging guarantee against a
real `AsyncAnthropic` instance with only its `.messages.parse` method replaced, deterministically
and with no network call. **Milestone 08's literal acceptance criterion — "one deterministic
test call produces a validated structured result and records usage metadata" — is proven this
way, against a fake response, not a real Anthropic API call: no real API key exists in this
environment.** See the Milestone 08 PR for what that leaves unverified.

Milestone 09 added `AnthropicGateway.create_message()` alongside `generate_structured()`: the
same call/error-classify/usage-record/telemetry path (factored into a shared `_call()` helper
once a second method needed it), but returning the SDK's own unparsed content blocks rather than
one validated result — what a tool-use loop needs to see a `tool_use` block and decide whether
to call a tool or stop. `colt_agents.AgentRuntime` is that loop; see
[`docs/architecture/AGENT_ARCHITECTURE.md`](./AGENT_ARCHITECTURE.md) for how it drives tools and
persists its audit trail.

## 8. Frontend

`apps/web` is a Next.js App Router application under `src/`, laid out per `CLAUDE.md` §43:

```text
apps/web/src/
  app/                  routes, layouts, error/loading/not-found boundaries
  features/<domain>/    per-feature page content (dashboard, leads, campaigns, ...)
  components/           shared shell and UI primitives
  lib/                  cn(), runtime config, the TanStack Query client factory
  hooks/                shared client hooks (e.g. useSystemHealth)
  api/                  the configured @colt/api-client instance
  styles/               globals.css and design tokens
```

`app/` stays thin — routing and metadata only. Page content lives in `features/<domain>/`, which
each route's `page.tsx` imports and renders. A feature with no backend yet (every one except the
probes, until Milestone 10 onward) renders an honest `EmptyState` naming the milestone that
populates it, rather than fabricated data (`CLAUDE.md` §0.4).

### Server/Client boundary

`app/(shell)/layout.tsx` wraps every product route in `AppShell` — sidebar, header, live system
health. Interactive pieces (`NavLink`, `SystemHealthBadge`) are Client Components; everything else
renders on the server by default.

One constraint bit us building this: React Server Components serialise the whole rendered tree
for the RSC payload (needed for client-side navigation), and a raw component reference is not a
serialisable value the moment it crosses into a Client Component's props — only a rendered
element is. `NAV_ITEMS` therefore stores icon _components_, but `AppShell` (Server) renders each
one to an element — `<item.icon ... />` — before handing it to `NavLink` (Client) as a prop. Passing
the bare component reference instead fails the production build with "Functions cannot be passed
directly to Client Components," only at build/prerender time, not in `next dev`.

### Data fetching

Server state goes through TanStack Query (`CLAUDE.md` §77) via the client in `src/api/client.ts`
for Client Components; Server Components should construct their own request-scoped client with
`createColtClient` rather than importing that shared instance (`CLAUDE.md` §5.1). No global store
mirrors backend state.

### API client

`@colt/api-client` is generated from the FastAPI OpenAPI schema — see
[ADR-0004](../decisions/ADR-0004-typed-api-client-generation.md) and
[`packages/typescript/api-client/README.md`](../../packages/typescript/api-client/README.md).
`pnpm --filter @colt/api-client generate` (or `make api-client`) regenerates it; the output is
committed so a fresh checkout typechecks without running Python first.

## 9. Data flow: the core product loop

_To be documented as Milestones 10–22 land. The loop is specified in `CLAUDE.md` §1.3._

## 10. Deployment topology

_To be documented in Milestone 25._
