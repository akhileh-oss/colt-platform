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

**Milestone 27 — Staging Soak Test: complete (see caveat below).**

`make dev` brings up the full local stack — Postgres with pgvector, Redis, Temporal and its UI,
MinIO, Mailpit, Keycloak and an OpenTelemetry collector — and verifies every service is serving.

The API authenticates every protected route against real Keycloak-issued JWTs, resolves the
caller's organization and role from the database rather than trusting the token, enforces
per-permission authorization, and scopes every tenant query through two independent layers — an
application-layer repository base class and PostgreSQL Row-Level Security, now covering all
twelve tenant-owned tables. `Organization`, `User`, `Company`, `Person`, `Signal`, `Evidence`,
`Lead`, `Campaign`, `Message`, `Conversation`, `Opportunity`, `CrmSyncRecord` and `AuditLog` are
real domain entities and database tables, with Alembic migrations and a seeded local dataset
(`make migrate && make seed`). A Temporal worker (`make worker`) runs real workflows against the
local Temporal server, with a proven-durable example workflow — killing the worker mid-workflow
and starting a fresh one still completes it correctly, from server-tracked state rather than
worker memory. Every request, workflow, activity and database query is traced with
OpenTelemetry and correlated by `trace_id` in structured JSON logs — proven by one real request
whose trace ID appears in both the API's own log line and a DB-touching Temporal activity's, in
a genuinely separate worker process.

The web app is a Next.js operator console with a persistent shell, navigation to every feature
area, and a typed client generated from that OpenAPI contract (`@colt/api-client`). The
dashboard's system health panel and the Campaigns page are real; every other feature page is an
honest placeholder — the schema, repositories and worker exist, but no route yet reads or writes
through them, and the web app has no login flow yet, so the Campaigns page itself cannot be
exercised in a live browser session here (every request 401s with no real bearer token to
attach) — it is verified by type-checking against the real generated schema and by the API's own
route tests instead.

`colt_ai.AnthropicGateway` is the one place allowed to call the Anthropic SDK directly: it routes
a `ModelClass` to a configured model ID, validates structured output against a Pydantic schema
server-side, records usage and cost from every response, classifies provider errors into Colt's
own error taxonomy, and never passes prompt or response content to a log line or span attribute.
`colt_agents.AgentRuntime` builds on it with a real tool-use loop: a typed tool (`colt_agents.
Tool`) is data — a name, a Pydantic schema, an async handler — and `ToolRegistry.for_agent`
statically filters which tools an agent's model call ever sees, before any model call happens.
Every run becomes one `AgentRun` row and one `ToolCall` row per tool invocation, written whether
the run succeeds or fails — a real, independently-queryable audit trail, not a log line.

`colt_agents.research_agent.RESEARCH_AGENT_DEFINITION` is the first of the ten product agents
(`CLAUDE.md` §12) actually built: given a company, it searches the web (`search_web`), fetches
pages (`fetch_page`, a real, SSRF-safe `HttpFetchProvider`), and records sourced claims as
`Evidence` rows (`record_evidence`, backed by `colt_application.RecordEvidence`) — proving the
full required path for real: `Claude → Typed Tool → Application Service → Repository →
PostgreSQL`. Its output schema, `ResearchDossier`, distinguishes `FACT` from `INFERENCE` from
`HYPOTHESIS` claims (§12.5), and a Pydantic validator makes it structurally impossible to
construct a `FACT` claim with no linked `evidence_id` — the acceptance criterion holds by
construction, not merely by prompt instruction.

`DiscoveryAgent` and `EnrichmentAgent` (`CLAUDE.md` §12.3-§12.4) are next: `DiscoveryAgent`
finds candidate companies/people (`search_companies`/`search_people`, backed by an
`EnrichmentProvider` — `FakeEnrichmentProvider` by default, a real `ApolloEnrichmentProvider`
verified against Apollo's own API docs) and deduplicates every result against already-known
records before creating anything, following `CLAUDE.md` §22's exact layered matching (provider
ID, then normalized email/LinkedIn URL, then company + normalized name gated by a confidence
threshold) — never on fuzzy name similarity. `EnrichmentAgent` resolves additional data for an
already-known company or person, and never lets a lower-confidence provider result silently
overwrite higher-confidence data already on file.

`SignalAgent` (`CLAUDE.md` §12.6) detects "why now" events: it polls pending raw trigger events
(`poll_signal_sources`, backed by `SignalTriggerSource` — `FakeSignalTriggerSource` is the
literal "mock trigger" Milestone 12's acceptance criterion names, since CLAUDE.md names no
specific real signal-source provider) and records the single strongest one it finds
(`record_signal`) with a `business_implication` — the model's own judgment, never a
deterministic computation. `colt_application.signals.rank_signal()` then scores it
deterministically from its own stored fields (signal-type weight × confidence × freshness
decay) — a pure function, not a persisted column, reproducible by anyone from the row alone.

`ScoringAgent` (`CLAUDE.md` §12.7, §21) enforces §21's hybrid-scoring rule in code: the agent
supplies only the two components that need judgment (`persona_fit`, `model_assessment`); three
more (`icp_fit`, `signal_strength`, `timing`) arrive as already-known deterministic facts; and
`score_lead` computes `overall_score` as §21's exact weighted baseline — never the model's own
arithmetic — plus deterministic `reason_codes` and a qualification decision reusing `LeadStatus.
QUALIFIED`/`NOT_QUALIFIED`. `LeadScore` (§10.8) is append-only — no `update()`, only `add()` —
so a lead's full scoring history, each row attributable to the `model_version` that produced
it, is never overwritten.
**One caveat, carried from Milestones 08-13:** no real Anthropic API key exists in this
environment, so every milestone built on `colt_ai.AnthropicGateway` proves its literal
acceptance criterion against a fake response at the `AsyncAnthropic` client boundary, not a real
network call (no real Apollo API key exists either). Every other line of the gateway's,
runtime's, and those milestones' own logic (routing, usage accounting, error classification,
telemetry, redaction, persistence, identity resolution, confidence precedence, ranking, scoring)
runs for real in those tests; only the actual provider round-trips are substituted.

`CampaignStatus` (`CLAUDE.md` §10.9, Milestone 14) is the first closed state machine CLAUDE.md
itself does not define for Campaign — unlike Lead, Conversation and Opportunity, §11 is silent
on it, so this milestone's own Build list item ("campaign state machine") and acceptance
criterion ("can be created, validated, paused, resumed, and inspected") are the specification:
`DRAFT → ACTIVE` only via `ValidateCampaign` (which checks a target-audience definition,
channels, schedule and limits are all present), `ACTIVE ⇄ PAUSED` via `PauseCampaign`/
`ResumeCampaign`, and `ACTIVE`/`PAUSED`/`COMPLETED → ARCHIVED` as the terminal state. This is
also the first real DB-backed CRUD REST resource in the API (`POST`/`GET /campaigns`,
`GET /campaigns/{id}`, and the three lifecycle actions), gated by `CAMPAIGN_WRITE` (create) and
`CAMPAIGN_LAUNCH` (validate/pause/resume) rather than one blanket permission, and the first real
frontend feature page beyond the dashboard's system health panel. No Anthropic call exists
anywhere in this milestone — there is nothing to leave unverified; its acceptance criterion is
proven in full against real Postgres. `SequenceStep` (`CLAUDE.md` §10.10) is a real table and
nested resource too (`/campaigns/{id}/sequence-steps`) — Milestone 14's own Build list names
"sequence steps" as its own deliverable, separate from Campaign's `channels` list, so this
milestone's review caught and closed that gap in the same PR rather than deferring it.

`PersonalizationAgent` and `MessagingAgent` (`CLAUDE.md` §12.8-§12.9, Milestone 15) turn a lead
and its recorded `Evidence` into a drafted outreach message, with "no unsupported personalization
claims" enforced structurally rather than merely by prompt instruction: `PersonalizationAgent`
must call `list_evidence_for_lead` before it can call `select_evidence`, and `select_evidence`
(`colt_application.SelectPersonalizationEvidence`) rejects any `evidence_id` that use case didn't
itself just return — an empty selection is rejected too, since a strategy with no cited evidence
is exactly the forbidden behavior §12.8 names. `MessagingAgent` then drafts the message
(`draft_message`, backed by `colt_application.DraftMessage`), independently re-validating every
`evidence_id` against the real `EvidenceRepository` before persisting anything, since each tool
call is model-decided input and the first validation does not guarantee the second tool call
reuses the same set. `Message` rows are append-only "versions" per `(lead_id, sequence_step_id)`
— drafting again for the same lead and step adds a new row rather than overwriting the last one,
the same reasoning `LeadScore` (§10.8) already established. Brand voice is read from
`Organization.settings["brand_voice"]`, falling back to a documented in-code default when unset —
CLAUDE.md names brand voice as model input without specifying its storage, so this is this
milestone's own documented design decision. The campaign router gained a read-only review
endpoint, `GET /campaigns/{id}/messages`, gated by `MESSAGE_APPROVE` (reusing the existing
permission rather than adding a redundant read-only one, since every role that can review a
message already carries it) — approving or rejecting a draft is Milestone 16's job, this
milestone only proves a message can be generated, persisted, and listed back out.

Milestone 16 builds the policy engine CLAUDE.md §17 describes conceptually
(`colt_policy.evaluate_outbound_send`) and wires it in front of the one use case allowed to
cause an external send, `SendMessage` — proving the literal acceptance criterion, "a policy
violation cannot result in an external message send," by showing the fake sender a test injects
is never called on any denied path. Twelve of §17.1's fifteen mandatory checks are modeled now
(suppression, channel/campaign/rate-limit/evidence/duplicate-send/approval/send-window); the
remaining three — contact-permission rules, provider-credential validity, and compliance checks
— have no represented infrastructure yet and are explicitly deferred rather than faked, the
same "document the gap" practice this project has followed since Milestone 10. `Approval`
(§10.17) and `SuppressionEntry` (§10.18) are new entities with their own tables and Row-Level
Security; `SuppressionEntry.organization_id` is nullable "for system-wide policy," so its RLS
policy is this milestone's own documented departure from the usual per-tenant pattern — a NULL
row is visible to every organization rather than none. `GET /campaigns/{id}/messages/{message_
id}/approve` and `/reject` (Milestone 16) finally make the message-review UI's buttons real;
`ENABLE_AUTO_APPROVAL` (§51) is a new typed feature flag, off everywhere by default, gating
whether a campaign's own `approval_policy: {mode: "auto"}` is even allowed to skip a human
decision. No Anthropic call exists anywhere in this milestone — there is nothing to mock; its
acceptance criterion is proven in full against real Postgres.

Milestone 17 builds the email subsystem (`CLAUDE.md` §29): `colt_integrations.email.
SmtpEmailProvider` is real SMTP (stdlib `smtplib`), speaking to local Mailpit by default and to
a real provider's relay when `FEATURE_REAL_EMAIL` is on — one class deliberately serves both the
"Mailpit adapter" and "real provider adapter behind feature flag" Build items, since CLAUDE.md
names no specific commercial email API the way it names Apollo or Brave, and SMTP is the one
wire protocol both targets speak. `EmailMessageSender` (the `MessageSender` port's first real
implementation) resolves §29.1's threading by looking up the most recent prior send to the same
lead/step and setting `In-Reply-To`/`References` from its stored `provider_message_id`, and sets
RFC 8058 one-click unsubscribe headers. `SendMessage` itself (Milestone 16) gained the
idempotency-key claim §24.4/§29.2 actually asks for: the key is computed from
`(campaign_id, lead_id, sequence_step_id)` and claimed only at successful send time, checked
against every message sharing that slot, not merely the one row being sent — a different
drafted version of the same lead/step that already sent once blocks a second send too.
`ProcessInboundEmail` resolves an incoming reply's `In-Reply-To` back to the `Message` Colt sent,
threads it onto that lead's `Conversation` (a real entity/table/port, named since Milestone 05
but never built until this milestone needed it), and appends a `message_received`
`ConversationEvent` (§10.13, also never built before now) — deliberately _not_ classifying what
the reply means, which is `ReplyIntelligenceAgent`'s job (Milestone 19). `ProcessBounce` and
`UnsubscribeByToken` both suppress the address through `AddSuppressionEntry` (Milestone 16's own
mechanism, reused rather than duplicated) and terminate the lead's conversation; the unsubscribe
link's "token" is the sent `Message`'s own id plus its `organization_id` (routing information, not
a credential — Row-Level Security requires binding a tenant before any lookup can even run), not
a signed scheme, since a UUIDv4 already has no public mapping back to a person. `SendEmailWorkflow`

- `send_email_activity` (`colt_workflows`) are the milestone's "send queue/workflow" Build item —
  the first real product workflow since Milestone 06's foundation example, running the exact same
  policy-gated `SendMessage` path behind Temporal's retry policy. A hard bounce has no real
  provider webhook to receive in this environment (same "no real X" posture as Milestone 12's
  signal sources) and Mailpit cannot generate one, so `ProcessBounce` is proven hermetically only.
  Everything else — draft, approve, send over real SMTP to Mailpit, read the send back through
  Mailpit's own REST API, send a simulated reply into the same local Mailpit, and thread it onto a
  real `Conversation`/`ConversationEvent` in Postgres — is proven end to end against real local
  infrastructure, never the public internet, which is this milestone's literal acceptance
  criterion.

Milestone 18 builds `LeadOutreachWorkflow` (`CLAUDE.md` §24.3), the first real product workflow
wiring the research/personalization/messaging agents into one durable, restart-safe path: load
state → validate qualification → research if stale/missing → personalize → draft → policy check
→ approval wait → send → response wait → sequence continuation. Rather than wiring every REST
route that can change an approval decision or a lead's conversation state to also push a Temporal
signal into a running workflow, approval-wait and response-wait are both polling loops over the
same Postgres rows `DecideMessageApproval` (Milestone 16) and `ProcessInboundEmail`/
`UnsubscribeByToken` (Milestone 17) already write — `workflow.sleep` between polls is still fully
durable, and this needs no changes to those already-shipped routes. The actual send reuses
`send_email_activity` (Milestone 17) unchanged rather than reimplementing `SendMessage`'s
policy-gated path a second time. No real Anthropic key exists in this environment (the caveat
carried since Milestone 08), so the workflow's own hermetic tests (`tests/workflows`) substitute
fake activities at the Temporal worker registration boundary, and its real-Postgres integration
tests prove `load_outreach_state_activity`'s eligibility/research/next-step logic and
`check_conversation_activity`'s reply/unsubscribe detection for real — "workflow survives
restarts" is covered by Milestone 06's own literal proof of the same underlying Temporal
mechanism this workflow's worker shares, since `LeadOutreachWorkflow` cannot reach a durable wait
state without a real model call to draft a message first.

Milestone 19 builds `ReplyIntelligenceAgent` (`CLAUDE.md` §12.10): it classifies one inbound
reply — intent, sentiment, urgency, objection, whether it asks a question or signals wanting a
meeting, a recommended conversation-state transition, confidence, and a suggested response a
human reads before ever sending it ("suggested response generation" is a Build item, never an
automated send). What actually happens to the `Conversation` is never the model's own
recommendation taken verbatim: `colt_application.reply_classification.determine_conversation_
transition` decides it deterministically — a HIGH-urgency reply always produces a `HUMAN_
HANDOFF` regardless of what was recommended, and a terminal conversation never reopens from a
later reply — which is what makes "high-intent replies produce the correct handoff" hold even if
the model forgets to ask for one itself. `LeadOutreachWorkflow` (Milestone 18) now calls the new
`classify_reply_activity` the moment it detects a reply, right before stopping the sequence — the
literal "if a reply is received: terminate automated sequence; classify reply" (§23.1). No real
Anthropic key exists in this environment, so `ReplyIntelligenceAgent` itself is proven
hermetically only; the deterministic transition logic the acceptance criterion actually turns on
is proven against real Postgres.

Milestone 20 builds the CRM sync path (`CLAUDE.md` §30): `CrmSyncRecord` tracks, per
`(organization_id, entity_type, entity_id, provider_name)`, how one Colt entity maps to one
external CRM object — provider name, provider account ID, provider object ID, sync status, last
synced at, last error — never a column on `Company`/`Person`/`Opportunity` themselves, the same
polymorphic reasoning `Evidence` (Milestone 02) already establishes. CLAUDE.md names no specific
real CRM vendor (unlike the search/enrichment providers named in §28.2), so — the same posture
Milestone 12's `SignalTriggerSource` already documents — only the `CRMProvider` port and its
`FakeCRMProvider` test double are built this milestone; it supports queued failure simulation
(`success`/`rate_limit`/`timeout`/`500`/etc., CLAUDE.md §93) and upserts by `(kind, external_id)`,
so a retry never creates a duplicate provider object. `sync_entity_to_crm_activity` is the one
composition root that actually calls the provider — loading the real `Company`/`Person`/
`Opportunity` row (or the caller's own fields, for a CRM `Task`, which Colt has no native entity
for), syncing it, and recording the outcome through `RecordCrmSyncOutcome`, a deterministic,
I/O-free upsert mirroring `RecordReplyClassification`'s role. `CrmReconciliationWorkflow` durably
re-drives a batch of targets through that activity; Temporal's own retry policy handles "sync
retries safely after recovery," and nothing else in the codebase calls into this workflow or its
activity synchronously, so "CRM outage does not break core Colt workflows" holds structurally —
both proven against real Postgres: a simulated outage syncing one `Company` does not stop
`RecordEvidence` from completing normally in the same test, and two simulated failures followed
by a successful retry against the same target leave exactly one `CrmSyncRecord` row, `SYNCED`,
with exactly one provider-side object ever created.

Milestone 21 builds the Opportunity engine (`CLAUDE.md` §10.14, §11.3, §12.11). §11.3 names
the pipeline's seven stages as "minimum lifecycle support" but — unlike Lead and Conversation —
never states which moves between them are legal, so `opportunity_state.OPPORTUNITY_TRANSITIONS`
is this milestone's own documented transition table: a straight line from `QUALIFIED` through
`DISCOVERY`/`EVALUATION`/`PROPOSAL`/`NEGOTIATION` to `WON`, with `LOST` reachable from any
non-terminal stage and neither `WON` nor `LOST` ever reopening. `OpportunityAgent` (§12.11)
judges one thing only — whether a positive conversation carries real commercial intent, and,
only when it does, an optional deal value it must always label `is_estimate=true` (no
configured override source exists in this environment to ever let a value go unlabeled) — then
calls `create_or_update_opportunity`. `CreateOrUpdateOpportunity` is what actually prevents a
duplicate: at most one open (non-`WON`/`LOST`) `Opportunity` per `company_id`, so a second
positive conversation with a company already being tracked updates the existing row (gaining a
value it didn't have) rather than spawning a second one — the literal mechanism behind "without
duplicate creation." `TransitionOpportunityStage` and `AssignOpportunityOwner` are the rest of
the pipeline's and owner-assignment's deterministic mutations; `summarize_pipeline`/
`summarize_revenue_by_source` are pure read-side aggregations backing the pipeline dashboard and
closed-won revenue attribution (grouped by `Opportunity.source`, CLAUDE.md's own silence on a
mechanism making this milestone's documented design call). `evaluate_opportunity_activity`
wires a real `AgentRuntime` running `OpportunityAgent` behind Temporal, called from
`LeadOutreachWorkflow` only when a reply's classification lands on `POSITIVE` — never every
reply. No real Anthropic key exists in this environment, so `OpportunityAgent` itself is proven
hermetically only; the deterministic dedup/state-machine logic the acceptance criterion actually
turns on — two positive triggers for the same company producing exactly one `Opportunity` row —
is proven against real Postgres.

Milestone 22 builds the Analytics + Learning Loop (`CLAUDE.md` §68): eight read-only reports
(funnel, ICP performance, trigger performance, message performance, channel performance, agent
cost, model performance, revenue outcomes) answering the milestone's own acceptance
criterion — "what segments, signals, personas, channels and message variants produce commercial
outcomes." Every report is a pure function (`colt_application.summarize_*`) over rows a
repository's new `list_all()` method reads back, never a persisted column, the same
`signals.rank_signal`/`revenue_attribution` pattern this package already establishes. None of
CLAUDE.md's named dimensions has a stored field for "segment," "message variant," or "persona,"
so this milestone makes three documented proxy calls: `Company.industry` stands in for segment
(ICP performance), `Message.prompt_version` for message variant, and `Person.seniority`
(resolved through `Lead.person_id`) for persona — folded into one `message_performance` module
since the acceptance criterion names "personas" without a dedicated Build item for it. Every new
analytics `Protocol` lives in its own narrow `colt_application/ports/analytics.py` (a
`list_all()`-only reader per entity) rather than widening the existing, widely-depended-on
`LeadRepository`/`CompanyRepository`/etc. ports — adding a method to those would have broken
every other use case's `Fake*Repository` test double across the codebase, since a concrete class
satisfies a `Protocol` structurally only when it has every method that `Protocol` declares. The
dashboard (`apps/web`) renders all eight reports as real, typed panels against the generated
OpenAPI schema. Every `summarize_*` function has its own hermetic unit tests; a real-Postgres
integration test (`tests/integration/test_analytics.py`) seeds a winning company (its own
industry, signal type, message variant/persona, and channel) against a non-converting one and
proves each report surfaces the winner's commercial outcome while the other stays at zero — the
acceptance criterion, literally exercised.

Milestone 23 builds the AI Evaluation System (`CLAUDE.md` §45.5, §46, §68): golden datasets,
regression evaluations, structured-output validation, evidence-grounding tests, prompt
comparison reports, model comparison reports, and cost/latency measurements, all answering the
milestone's own acceptance criterion — "prompt/model changes can be evaluated before release."
The reusable mechanism — `EvalReport`, regression comparison against a stored baseline, prompt/
model comparison, evidence-grounding checks — lives in a new `colt_agents.evals` module;
`tests/evals/` holds the actual golden suites that drive it against three agents through the
real `AgentRuntime`, hermetically: `ScoringAgent` (structured-output validation — a response
missing a required field must be caught as a scored failure, never silently accepted; scoring
consistency; a regression gate against a stored `tests/evals/baselines/scoring_agent.json`),
`ResearchAgent` (evidence grounding — a `FACT` claim citing a fabricated evidence_id that
`record_evidence` never actually recorded is caught as a hallucinated citation, a failure mode
`DossierClaim`'s own schema validator cannot catch on its own), and `ReplyIntelligenceAgent`
(classification accuracy, including the deterministic `HIGH`-urgency override that always wins
over the model's own recommendation). Cost and latency are never a new measurement bolted onto
these suites — they reuse Milestone 22's own `summarize_agent_cost`/`summarize_model_performance`
directly over the real `AgentRun` rows an eval run produces, since an eval run is itself a
legitimate source of those rows. The prompt/model comparison suite runs the same `ScoringAgent`
golden set twice — once under two different `AnthropicSettings.model_fast` overrides (a real
cost delta from real Anthropic pricing, no regression), once under two `prompt_version` labels
with a deliberately, documented-ly simulated consistency regression between them (there is no
real prompt text to actually change here — no real Anthropic key exists in this environment, the
Milestone 08 caveat carried into this milestone too) — and asserts the comparison report catches
exactly that regression. `make eval` (`pytest -m evals`) runs the whole suite.

Milestone 24 hardens the API against `CLAUDE.md` §40's security baseline, closing five concrete
gaps a focused audit found rather than re-asserting controls already in place (SSRF protection,
tenant isolation on most tables, and input validation at the API boundary all pre-date this
milestone). **Rate limiting** (§37, §79) is new: `colt_api.rate_limit.RateLimiter` is a
Redis-backed fixed-window counter, wired as one `Depends(rate_limit(...))` on exactly one
route — the deliberately unauthenticated `POST /unsubscribe/{organization_id}/{message_id}`
webhook, keyed by that pair rather than client IP — because every other route in §79's five
rate-limited categories is either delegated to Keycloak (authentication), runs inside a Temporal
workflow rather than synchronously inside an HTTP handler (AI/search), or already has its own
throttle (`colt_policy.outbound`'s per-campaign send limiter). **Audit completeness** (§48): a
campaign's `ValidateCampaign` (its first `DRAFT`→`ACTIVE` transition — the only "launch" this
codebase has), `PauseCampaign`, and `ResumeCampaign` each now write a real `AuditLog` row
attributed to the acting user, closing the two named gaps (campaign launch/pause) the audit
found still missing. **Input limits**: `Campaign.name`, `Company.name`, and `Person.full_name`
now reject a value past 300 characters and `Message.subject` past 500 — each matching its
backing `String(N)` database column exactly, so the domain layer never claims a looser bound than
Postgres enforces — while `Company.description` and `Message.body` (both unbounded `Text`
columns) get their own deliberately tighter, documented application-level caps (5,000 and
100,000 characters). **`tests/security/`** is a new, dedicated regression suite (`make
test-security`, requires `make dev` + `make migrate`): an SSRF sentinel over the existing guard's
core invariant, four cross-tenant-deny tests closing coverage gaps on `approvals`, `lead_scores`,
`conversation_events`, and `crm_sync_records`, a full `(Role, Permission)` authorization matrix
exercised through the real `require_permission` dependency chain, a security-headers/redaction
sentinel, and a real-Redis proof of the rate limiter. Two findings were investigated and
documented as out of scope rather than silently dropped: **secure file handling** is not
applicable — no upload or file-serving endpoint exists anywhere in this codebase — and a
DNS-rebinding window in the SSRF guard (the resolved IP is checked once but the HTTP client
re-resolves at connection time) is an accepted, explicitly documented residual risk, since closing
it needs a custom `httpx` transport and `ResearchAgent` — the SSRF guard's only caller — never
fetches arbitrary user-supplied URLs, only ones a search provider already returned.

Milestone 25 builds the Production Infrastructure (`CLAUDE.md` §53, §68) as real Terraform:
`infrastructure/terraform/modules/` holds one leaf module per concern — networking (VPC,
public/private subnets, security groups), database (RDS Postgres with `pgvector`/`pgcrypto`),
cache (ElastiCache Redis), object storage (S3, the managed equivalent of local MinIO), secrets
(Secrets Manager, every value a placeholder an operator replaces by hand — CLAUDE.md §53's
"never store production infrastructure secrets in Git"), compute (ECS Fargate for `api`/`web`/
`worker`, an ALB, an ADOT collector sidecar in every task so OpenTelemetry tracing survives the
move off `docker-compose.yml`'s local collector), Temporal (self-hosted on ECS Fargate against
the same RDS instance, `temporalio/auto-setup`'s own startup mechanism creating its databases —
this milestone's documented choice over Temporal Cloud, which needs an external account this
project doesn't have), DNS/TLS (Route53 + ACM), observability (a CloudWatch dashboard),
alerting (SNS + alarms on RDS CPU/storage/connections, ALB 5xx rate, and ECS task health), and
backups (an AWS Backup plan with its own documented retention, alerting on a failed backup job —
§54's required "restore testing" is explicitly Milestone 28's job, not this one's).
`infrastructure/terraform/environment/` composes every leaf module into one environment;
`infrastructure/environments/staging/` and `.../production/` are each their own Terraform root
— separate state, separate backend, separate provider configuration — calling that same
composition with different sizing, so the two can never silently drift in how the pieces wire
together, only in how big each one is. **Milestone 25's literal acceptance criterion —
"staging environment can be created reproducibly from Terraform with no manual undocumented
infrastructure steps" — could not be proven by an actual `terraform apply`:** this sandbox has
no real AWS account to provision against, so `plan`/`apply` are `NOT RUN`. What was verified
instead: `terraform fmt -check` (clean), and `terraform init -backend=false` + `terraform
validate` for `bootstrap/`, `environments/staging/`, and `environments/production/` (all three
valid) — proving every module's syntax, type, and reference graph is internally consistent, the
static half of "reproducible," without the real-infrastructure half this environment cannot
supply.

Milestone 26 builds CI/CD (`CLAUDE.md` §68) as a GitHub Actions pipeline (`.github/workflows/
ci.yml`) running every stage the Build list names, each its own job: `install-lint-typecheck`,
`security` (`make security`), `unit-tests`, `integration-and-workflow-tests` (`make dev` + `make
migrate` + `test-integration`/`test-workflows`/`test-security` — the identical commands a
contributor runs locally, not a parallel GitHub Actions `services:` block that could silently
drift from them), `e2e-tests` (Playwright's own `webServer` config starts the API and web app
itself), `migration-validation` (`alembic check` against a fresh database — fails if a `colt_db`
model changed without a matching migration), `build-images` (new `apps/api/Dockerfile`,
`apps/web/Dockerfile`, `infrastructure/docker/worker/Dockerfile`, pushed to ECR via AWS OIDC —
no long-lived AWS key stored in this repository), `deploy-staging` (`terraform apply` against
the Milestone 25 staging environment), and `smoke-test-staging` (an unauthenticated `GET
/api/v1/meta` through the ALB's `/api/*` route, and `GET /` through its `/*` route — proving
both the `api` and `web` services are actually reachable, not just that ECS reports them
healthy). `build-images`/`deploy-staging`/`smoke-test-staging` run only on a push to `main`; a
draft PR's own CI never touches a real image registry or staging itself.

**Production deployment requires an explicit release step** (`CLAUDE.md` §56): a second
workflow, `.github/workflows/deploy-production.yml`, triggers only on `workflow_dispatch` — a
human choosing an already-built, already-staging-soaked image tag from the Actions tab, never a
push or a schedule — and its deploy job declares `environment: production`, gating it behind
this repository's own "production" GitHub Environment protection rule. That rule (a required
reviewer) is configured in the repository's Settings, not in a workflow file Terraform or this
PR can create — documented here as a one-time setup step a repo admin must still perform, rather
than silently assumed already in place.

Building the Dockerfiles surfaced one real finding, fixed in this milestone rather than carried
forward: `migration-validation`'s own new `alembic check` step caught genuine schema drift
predating the Milestone 05 naming-convention change — the `campaigns` table's status check
constraint was named `valid_campaign_status` in its original migration but compiles to
`ck_campaigns_valid_campaign_status` under `colt_db.base`'s naming convention today, and two
JSON columns (`conversation_events.event_metadata`, `sequence_steps.conditions`) were migrated
as generic `JSON` though their models have declared `JSONB` for some time. A new migration
(`ee0e282d11ae`) reconciles both, verified upgrade-then-check-then-downgrade-then-upgrade
against a real, disposable Postgres database.

**What could not be verified here, and why**: this sandbox's shared network egress is
rate-limited by Docker Hub (`429 Too Many Requests` resolving `python:3.12-slim`/every
`docker.io` base image), so an actual containerized `docker build` of any of the three new
Dockerfiles was `NOT RUN`. Every build step's own underlying command was still verified for
real, outside a container: `uv sync --frozen --no-dev --no-install-project` and `uv sync
--frozen --no-dev` (api), `uv sync --frozen --no-dev --package colt-workflows` (worker), and
`pnpm --filter @colt/web build` (web, confirming `next.config.ts`'s new `output: "standalone"`
produces exactly the `apps/web/.next/standalone/apps/web/server.js` path the Dockerfile's
runtime stage expects) all succeed. GitHub Actions' own runners pull from Docker Hub without
this sandbox's shared-IP throttling, so the real containerized build is expected to succeed
there; it is reported as unverified here rather than assumed passing.

Milestone 27 builds the Staging Soak Test (`CLAUDE.md` §96, §68) against reality: this sandbox
has no real deployed staging environment (Milestone 25's Terraform was never `apply`'d), so the
literal acceptance criterion — "no data corruption, duplicate sends, cross-tenant access, or
unrecoverable workflows" under thousands of mocked leads, worker/API restarts, DB/Redis
failures, and provider throttling, run in staging — cannot be claimed here. What this milestone
actually did: `tests/soak/` (`make test-soak`) runs real chaos and volume scenarios against
real local Postgres/Redis at a smaller, CI-practical scale — identity-resolution concurrency,
a real Postgres container restart, a real Redis container restart, duplicate unsubscribe-
webhook delivery, and volume + tenant isolation under concurrent writes — and **found two real,
previously-undiscovered concurrency bugs**: `DiscoverCompany`/`DiscoverPerson` could create
duplicate `Company`/`Person` rows when two discoveries of the same domain/email raced each
other (ten concurrent calls produced ten and nine duplicate rows respectively, reproduced
before being fixed), and a duplicate unsubscribe-webhook delivery raised a raw, unhandled
database error instead of the clean `204` the route's own docstring had always promised. Both
are fixed for real: two new partial unique indexes plus a `colt_domain.DuplicateIdentityError`
the `colt_db` repository layer translates database conflicts into, and a `SAVEPOINT`-based
idempotent recovery in `SqlAlchemySuppressionRepository.add()`. `tests/soak/load/
locustfile.py` is the tool for the literal "thousands... in staging" run — built, verified to
generate real HTTP load against a real running API in this sandbox — but genuinely **not run
against staging**, since no staging exists here; `docs/operations/RUNBOOK.md` §6 is the actual
procedure for running it for real once Milestone 25's infrastructure is applied.

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
| 09        | Agent runtime + tool registry         | ✅ Complete (see caveat above) |
| 10        | Research + evidence                   | ✅ Complete (see caveat above) |
| 11        | Discovery + enrichment                | ✅ Complete (see caveat above) |
| 12        | Signal engine                         | ✅ Complete (see caveat above) |
| 13        | Lead scoring + qualification          | ✅ Complete (see caveat above) |
| 14        | Campaign engine                       | ✅ Complete                    |
| 15        | Personalization + messaging           | ✅ Complete (see caveat above) |
| 16        | Policy + approval system              | ✅ Complete                    |
| 17        | Email subsystem                       | ✅ Complete (see caveat above) |
| 18        | Outreach workflow                     | ✅ Complete (see caveat above) |
| 19        | Reply intelligence                    | ✅ Complete (see caveat above) |
| 20        | CRM integration                       | ✅ Complete                    |
| 21        | Opportunity engine                    | ✅ Complete (see caveat above) |
| 22        | Analytics + learning loop             | ✅ Complete                    |
| 23        | AI evaluation system                  | ✅ Complete                    |
| 24        | Security hardening                    | ✅ Complete                    |
| 25        | Production infrastructure             | ✅ Complete (see caveat above) |
| 26        | CI/CD + release engineering           | ✅ Complete (see caveat above) |
| 27        | Staging soak test                     | ✅ Complete (see caveat above) |
| 28–30     | See [`CLAUDE.md` §68](./CLAUDE.md)    | Not started                    |

**Oracle Cloud "Always Free" deployment** (not a `CLAUDE.md` milestone — a user-requested, $0/
month alternative to Milestone 25's AWS infrastructure, for anyone who cannot carry AWS's
recurring NAT Gateway/ALB/Fargate costs, none of which has a free tier at any usage level).
`infrastructure/terraform/oracle/` + `infrastructure/environments/oracle-free/` provision one
Always Free Ampere A1 instance (4 OCPU/24GB — the entire Always Free compute allowance) running
the same `docker compose` stack Milestone 00's local dev already proves works, with a dedicated
backed-up block volume, a reserved public IP, and Caddy for automatic HTTPS. The real trade for
$0: one box, no managed multi-AZ failover — if it goes down, the app goes down until it's back.
See [`docs/operations/ORACLE_FREE_TIER_DEPLOYMENT.md`](./docs/operations/ORACLE_FREE_TIER_DEPLOYMENT.md)
for account setup, costs that are and aren't actually free, and the backup/restore procedure.
This Terraform has been `fmt`/`validate`-checked, same as Milestone 25's AWS Terraform, but
never `apply`'d against a real OCI tenancy in this sandbox (no OCI account exists here) — it is
reported as unverified-by-apply rather than assumed working end-to-end.

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
