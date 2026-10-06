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

`routers/v1/campaigns.py` (Milestone 14) is the first router to actually read and write through
this whole path end to end — every prior endpoint either had no persistent state (`/me`,
observability's trace-check) or was reached through an agent's tool-use loop instead of HTTP.
Each route depends on `DbSessionDep` and one of three `require_permission(Permission.X)`-backed
principal aliases, constructs a `SqlAlchemyCampaignRepository` scoped to the caller's own
organization, and drives a `colt_application` use case — the router itself holds no business
logic, same as every other module in this package. `Campaign`'s state machine (`DRAFT →
ACTIVE → PAUSED/COMPLETED/ARCHIVED`) is this milestone's own design decision: `CLAUDE.md` §11
defines one for Lead, Conversation and Opportunity but is silent on Campaign. The same router
nests `SequenceStep` (§10.10) under `/campaigns/{id}/sequence-steps` — a table and resource
this milestone's own Build list names separately from Campaign's `channels` list, caught
missing on review and closed in the same PR.

Milestone 15 adds `GET /campaigns/{id}/messages`, a read-only list of a campaign's drafted
`Message` rows gated by `Permission.MESSAGE_APPROVE` — reusing that permission rather than
adding a redundant read-only one, since every role that can review a message already carries it.
It is the first route reached only after an agent pipeline (`PersonalizationAgent` →
`MessagingAgent`, see [`AGENT_ARCHITECTURE.md`](./AGENT_ARCHITECTURE.md) §12) has already
persisted the rows it lists; the route itself still holds no business logic, calling
`colt_application.ListMessages` like every other router method here.

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

## 11. Policy engine (Milestone 16)

`colt_policy.evaluate_outbound_send()` (`CLAUDE.md` §17) is a pure function, not a service: it
takes an `OutboundSendContext` of already-resolved booleans and returns a `PolicyEvaluation`
(`ALLOW`/`DENY`/`REQUIRE_APPROVAL`/`DEFER` plus which checks failed). `colt_policy` depends only
on `colt_domain` (see the package map in §3), so it cannot reach a database, a clock, or a
provider itself — gathering the facts to evaluate is the caller's job. That caller is
`colt_application.SendMessage`, the one use case allowed to invoke `MessageSender.send`, and
only after the engine returns `ALLOW`. This is the literal mechanism behind Milestone 16's
acceptance criterion, "a policy violation cannot result in an external message send": the send
call sits _after_ the policy check in the same function, never reachable from a denied branch,
so a test can assert a fake sender was never invoked rather than merely that an error was
raised.

Twelve of §17.1's fifteen mandatory checks are modeled today (lead/organization match, target
identity validity, suppression, channel/campaign-status/rate-limit/evidence/duplicate-send,
approval, send-window). The remaining three — contact-permission rules, provider-credential
validity, and compliance checks — have no represented infrastructure yet (no real channel
provider exists before Milestone 17's email subsystem) and are deliberately left unmodeled
rather than represented by an always-true stub; `colt_policy.outbound`'s own module docstring
names them.

`Approval` (§10.17) and `SuppressionEntry` (§10.18) are new tenant-owned tables with the usual
Row-Level Security, with one departure: `SuppressionEntry.organization_id` is nullable "for
system-wide policy" (§10.18's own words), so its RLS policy is `organization_id = current_
setting(...) OR organization_id IS NULL` rather than the equality-only policy every other table
uses — a NULL-organization row is meant to be visible to every tenant, not hidden from all of
them. `SqlAlchemySuppressionRepository.is_suppressed()` likewise queries both an organization's
own entries and every global one in a single call, rather than going through
`TenantScopedRepository._select_scoped()`'s strict equality filter.

## 12. Email subsystem (Milestone 17)

`colt_integrations.email` is the first real `MessageSender` channel adapter: `SmtpEmailProvider`
(real `smtplib`, wrapped in `asyncio.to_thread`) and `EmailMessageSender` (the port
implementation `SendMessage` calls) sit at the `colt_integrations`/`colt_agents` layer, exactly
where §5's layering puts a real adapter — `colt_application` never imports either; it only
depends on the `MessageSender` Protocol, satisfied structurally. `EmailMessageSender` resolves
§29.1's threading itself: before sending, it looks up every prior message to the same `(lead_id,
sequence_step_id)` and threads off the most recent one with a stored `provider_message_id`,
setting `In-Reply-To`/`References` — "incoming messages must resolve to the correct Colt
conversation" starts with the outgoing message carrying a thread id to resolve _against_.

`SendMessage` claims the idempotency key §24.4/§29.2 describes — `f"{campaign_id}:{lead_id}:
{sequence_step_id}"` — only at the moment a send actually succeeds, via `update_send_result`,
never at draft time: the database's own partial unique index on `(organization_id,
idempotency_key) WHERE idempotency_key IS NOT NULL` would raise on the second drafted version of
the same lead/step if every draft claimed it uniformly. The check itself is cross-row: `get_by_
idempotency_key` is queried against every message sharing that slot, not merely re-checked
against the one row being sent, so a different drafted version that already completed a send
blocks this one too.

`ProcessInboundEmail`/`ProcessBounce`/`UnsubscribeByToken` (`colt_application`) are §29's inbound
leg. All three depend only on ports (`MessageRepository`, `ConversationRepository`,
`ConversationEventRepository`, `LeadRepository`, `PersonRepository`, and `AddSuppressionEntry`
reused rather than duplicated) — never on `colt_integrations` directly, the same inward-only
dependency direction every other use case holds. `MailpitInboxClient` (`colt_integrations`) is
what actually reads a reply back out of Mailpit's REST API; the REST endpoint
(`routers/v1/unsubscribe.py`) and the Temporal activity (`send_email_activity`,
`colt_workflows`) are the two places that construct the real adapters and call into these use
cases — composition roots, same as every other use case's wiring.

`send_email_activity` opens its own tenant-scoped session (`colt_workflows` is the one layer
allowed to depend on both `colt_application` and `colt_integrations` at once, per §5's layer
map) and runs the same `SendMessage` path a direct `SendMessage` call would, behind Temporal's
retry policy — `NotFoundError`/`PolicyDeniedError` are non-retryable (retrying repeats the same
denial); a `ProviderError`'s own `.retryable` flag decides everything else. `SendEmailWorkflow`
is the first real product workflow since Milestone 06's foundation example; `LeadOutreachWorkflow`
(§24.3, Milestone 18) is a separate, broader sequencing workflow this one's single-message send
leg will eventually sit inside.

Milestone 17's acceptance criterion — "local full outbound lifecycle works without touching the
public internet" — is proven by `tests/integration/test_email_subsystem.py`: draft → approve →
send over real SMTP to a local Mailpit → read the send back through Mailpit's own REST API →
send a simulated reply into the same local Mailpit (exploiting its catch-all nature) →
`ProcessInboundEmail` → a real `Conversation`/`ConversationEvent` row in Postgres, entirely over
`localhost`. A hard bounce has no real provider webhook in this environment and Mailpit cannot
generate one, so `ProcessBounce` is proven hermetically only — the same "no real X" posture
Milestone 12 documented for signal sources.

## 13. Outreach workflow (Milestone 18)

`LeadOutreachWorkflow` (`colt_workflows`) is §24.3's conceptual workflow built for real: load
state → validate qualification → research if stale/missing → personalize → draft → policy check
→ approval wait → send → response wait → sequence continuation. Every step that performs a side
effect is its own activity (§24.1's "workflows must not perform raw network calls or database
access directly"); the workflow itself only branches on each activity's returned state and
sleeps between polls. `load_outreach_state_activity` reads the lead's current status, campaign
status, suppression state, the company's evidence freshness, and which sequence step (if any)
hasn't been sent yet — everything the workflow needs to decide what to do next, gathered once per
loop iteration rather than scattered across several smaller activities.

`research_company_activity` and `draft_next_message_activity` are the first activities to wire a
real `AgentRuntime` — ResearchAgent, then PersonalizationAgent and MessagingAgent in sequence —
behind Temporal rather than a direct application-layer call, following `colt_workflows`'
established "activity opens its own tenant-scoped session and composes real adapters" shape
(`send_email_activity`, Milestone 17). `activity.info().workflow_id`/`.workflow_run_id` are
passed through to `AgentRuntime.run()` so each resulting `AgentRun` row traces back to the
workflow execution that produced it — closing a gap no prior milestone needed, since no earlier
workflow ever invoked an agent.

Approval-wait and response-wait are both polling loops, not Temporal signals: rather than wiring
the existing `POST .../approve` route and the `ProcessInboundEmail`/`UnsubscribeByToken` call
sites to also push a signal into whichever `LeadOutreachWorkflow` execution corresponds to that
lead, the workflow itself re-checks the same Postgres rows those paths already write
(`Message.approval_status` via `send_email_activity`'s own `PolicyDeniedError` surfacing as a
retryable "pending approval" condition; `Conversation.last_activity_at`/`Lead.status` via
`check_conversation_activity`), sleeping between checks with `workflow.execute_activity`'s normal
retry policy. This changes nothing about Milestone 16/17's already-shipped routes and is no less
durable — `workflow.sleep` is tracked by the Temporal server exactly like every other awaited
point in the workflow.

The acceptance criterion — "workflow survives restarts, does not duplicate sends, and reacts
correctly to replies/unsubscribes" — is proven in three different ways, each at the layer where
it is actually provable in this environment. "Does not duplicate sends" is `SendMessage`'s own
cross-row idempotency check (Milestone 16/17's own proof, composed unchanged here — nothing new
to re-prove). "Reacts correctly to replies/unsubscribes" is proven against real Postgres in
`tests/integration/test_lead_outreach_activities.py`, calling `load_outreach_state_activity`/
`check_conversation_activity` directly as plain coroutines (neither touches `activity.info()`,
so this needs no running worker) against seeded Lead/Conversation/SuppressionEntry rows. "Survives
restarts" is covered by Milestone 06's own literal subprocess-kill proof of the underlying
Temporal mechanism (workflow state lives in the server, not worker process memory) — this
workflow's worker registration shares that exact mechanism, and `LeadOutreachWorkflow` itself
cannot reach a durable wait state without first drafting a message, which needs a real
Anthropic call no key in this environment can make; re-running Milestone 06's subprocess test
against this specific workflow would only exercise the Temporal SDK a second time.

## 14. Reply intelligence (Milestone 19)

`ReplyIntelligenceAgent` (`colt_agents`, CLAUDE.md §12.10) classifies one inbound reply into
`intent`, `sentiment`, `urgency`, `objection`, `asks_question`, `meeting_signal`, a
`recommended_state_transition`, `confidence`, and a `suggested_response` — §12.10's own minimum
output schema, verbatim. `ReplyIntent`/`Sentiment` are closed enums this milestone itself
defines (CLAUDE.md gives no vocabulary for either), the same "model names a field without
enumerating values, so the milestone building it makes the documented call" pattern
`CampaignStatus` (Milestone 14) and `Urgency` (`colt_application.reply_classification`) already
establish. `recommended_state_transition` is validated against a subset of `ConversationState` —
every value except `OPEN` (never a destination) and `UNSUBSCRIBED` (an explicit unsubscribe
link/request is its own mechanism, never a reply classification's guess).

The one write tool this agent may call, `record_reply_classification`, never applies
`recommended_state_transition` as the state actually set on the `Conversation` row.
`colt_application.reply_classification.determine_conversation_transition` decides that
deterministically — the same "model judges, code decides" split `ScoringAgent` (§12.7,
Milestone 13) already established for lead scoring. Two rules the model's own recommendation
can never override: a terminal conversation (`UNSUBSCRIBED`/`HUMAN_HANDOFF`) never moves again
from a later reply, and a `HIGH`-urgency reply always produces `HUMAN_HANDOFF` regardless of
what was recommended. This is the literal mechanism behind "high-intent replies produce the
correct handoff" holding deterministically — it does not depend on the model remembering to
recommend a handoff itself. `RecordReplyClassification` records a `reply_classified`
`ConversationEvent` carrying every §12.10 field plus the suggested response (read by a human,
never auto-sent), and — only when the applied transition actually lands on `HUMAN_HANDOFF` — a
second, distinct `handoff_created` event, since §10.13 lists both as their own event types.

`classify_reply_activity` (`colt_workflows`) wires a real `AgentRuntime` running
`ReplyIntelligenceAgent` behind Temporal, the same composition-root shape `research_company_
activity`/`draft_next_message_activity` (Milestone 18) already established — it opens its own
tenant-scoped session, reads the reply's own content from the most recent `message_received`
`ConversationEvent` (`ProcessInboundEmail`, Milestone 17, already stores `from_email`/`subject`/
`body` there), and constructs a real `AnthropicGateway`. `LeadOutreachWorkflow` calls it the
moment `check_conversation_activity` detects a reply, immediately before returning its
`REPLIED` outcome — the literal "if a reply is received: terminate automated sequence; classify
reply" (§23.1). This is the first real caller `ProcessInboundEmail`'s own reply-ingestion path
has had since Milestone 17 built it with none.

Milestone 19's acceptance criterion — "incoming replies update the conversation state
deterministically and high-intent replies produce the correct handoff" — is proven at two
layers. The deterministic transition logic itself (the literal subject of the acceptance
criterion) is proven against real Postgres in `tests/integration/test_reply_intelligence.py`:
a HIGH-urgency reply always produces a handoff regardless of the recommended state, a LOW-
urgency reply applies the model's own recommendation with no handoff, and a reply to an
already-unsubscribed conversation never reopens it. `ReplyIntelligenceAgent` itself is proven
hermetically only (`packages/python/colt-agents/tests/test_colt_agents_reply_intelligence_
agent.py`) — no real Anthropic key exists in this environment, the same caveat carried since
Milestone 08.

## 15. CRM integration (Milestone 20)

`CrmSyncRecord` (`colt_domain`, CLAUDE.md §30) is a new polymorphic entity, not a column on
`Company`/`Person`/`Opportunity` — the same reasoning `Evidence` (Milestone 02) already
establishes for a row that needs to reference any of several entity types generically. It
tracks `(organization_id, entity_type, entity_id, provider_name)` — unique, so a second sync of
the same entity against the same provider upserts the existing row rather than creating a
duplicate mapping — plus the exact fields §30 names: provider account ID, provider object ID,
`sync_status` (a milestone-defined closed enum, `PENDING`/`SYNCED`/`FAILED` — CLAUDE.md names the
field without enumerating values, the same "the milestone building it makes the documented call"
pattern `CampaignStatus` and `Urgency` already establish), last synced at, and last error.

CLAUDE.md names `CRMProvider` as the adapter and contact/company/opportunity/task sync as
separate Build items, but no specific real CRM vendor (unlike the search/enrichment providers
§28.2 names) — the same situation `SignalTriggerSource` was in for Milestone 12. Only the port
(`colt_integrations.crm.port.CRMProvider`) and its test double
(`colt_integrations.crm.fake.FakeCRMProvider`) are built this milestone; `CRMSettings.provider`
already defaults to `"fake"` (scaffolded ahead of this milestone in `colt_config`). Every sync
call is keyed by `external_id` — the calling Colt entity's own id as a string — so CLAUDE.md
§30's "CRM sync must be idempotent" holds by construction: `FakeCRMProvider` upserts by
`(kind, external_id)`, never creating a second provider object for a retry of the same target.
It also supports the "failure simulation" CLAUDE.md §93 calls essential for resilience testing —
`queue_failure(kind, external_id, error)` makes the next sync call for that target raise instead
of succeeding, once — which is what the acceptance test below drives directly.

`RecordCrmSyncOutcome` (`colt_application`) is the deterministic, I/O-free half: given a sync
attempt's result (a `provider_object_id` on success, an error message on failure), it upserts
the `CrmSyncRecord` row by `(entity_type, entity_id, provider_name)` and marks it `SYNCED` or
`FAILED` — the same "pure persistence logic, no I/O against the external system" role
`RecordReplyClassification` (Milestone 19) plays for conversation state. `sync_entity_to_crm_
activity` (`colt_workflows`) is the one composition root that actually calls the provider: it
opens its own tenant-scoped session (the established `send_email_activity`/`research_company_
activity` shape), loads the real `Company`/`Person`/`Opportunity` row to build the fields to
sync (or uses the caller's own `fields` for a CRM `Task`, which Colt has no native entity for),
calls the configured `CRMProvider`, and records the outcome through `RecordCrmSyncOutcome`
before returning or re-raising — so the `CrmSyncRecord` row is the durable account of what
happened independent of whether Temporal keeps retrying. A `ProviderError` is retried according
to its own `.retryable` classification (§28.1), the same rule `send_email_activity` applies to
the SMTP adapter.

`CrmReconciliationWorkflow` is the "reconciliation workflow" Build item: it durably re-drives a
batch of `CrmSyncTarget`s through `sync_entity_to_crm_activity`, one `RetryPolicy`-governed
activity call per target, collecting each outcome rather than letting one target's exhausted
retries abort the rest of the batch.

Milestone 20's acceptance criterion — "CRM outage does not break core Colt workflows; sync
retries safely after recovery" — is proven in two parts, against real Postgres in
`tests/integration/test_crm_sync.py`. The first half is structural: nothing else in the codebase
calls into `sync_entity_to_crm_activity` or `CrmReconciliationWorkflow` synchronously, so a CRM
outage can only ever stall this one path, never a caller — proven literally by running
`RecordEvidence` against the same company a simulated CRM outage just failed to sync, in the
same test, and showing it completes normally. The second half is `sync_entity_to_crm_activity`
called directly as a plain coroutine (it never touches `activity.info()`, the same legitimate
shortcut `test_lead_outreach_activities.py` already documents): two queued provider failures
followed by a successful call leave exactly one `CrmSyncRecord` row, `SYNCED`, with exactly one
provider-side object ever created — the literal "retries safely after recovery, no duplicate
side effects" (§96).
